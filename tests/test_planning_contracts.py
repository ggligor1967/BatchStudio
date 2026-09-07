"""PRODUCT-D1-I1 acceptance through actual planners and existing UI consumers."""
from dataclasses import FrozenInstanceError, replace
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import tempfile

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf._page import PageObject

from core.contracts import (
    ArtifactDescriptor, CheckOutcome, OperationPlan, PlanDiagnostic, PlanningContext,
)
from core.operations import OperationRegistry
from core.operations.base import Operation
from core.operations.file_ops import FileRenameOperation
from core.operations.image_ops import ImageConvertOperation
from core.operations import ocr_ops
from core.planning import PlanningSession, plan_file
from core.processor import BatchProcessor, process_single_file, MAX_FILE_SIZE
from core.security import OutputPathAllocator
from core.workflow import Workflow
from tests.test_dry_run_contracts import forbid_output_writes, filesystem_snapshot, make_source
from ui.logs_panel import LogsPanel
from ui.run_panel import RunPanel
from ui import run_panel


def workflow(*steps):
    result = Workflow("planning")
    for operation, config in steps:
        result.add_step(operation, config)
    return result


def run_plan(source, steps, out, **kwargs):
    return BatchProcessor(2).process_batch([str(source)], steps, str(out), dry_run=True, **kwargs)


def diagnostic(plan, check_id, outcome=None):
    return [check for check in plan['diagnostics'] if check['check_id'] == check_id
            and (outcome is None or check['outcome'] == outcome)]


def assert_conditional(stats):
    assert stats.failed_files == 0 and stats.processed_files == 1
    assert stats.planning_summary['CONDITIONAL'] == 1
    assert stats.execution_state == 'COMPLETED'
    plan = stats.plan_results[0]
    assert plan['success'] and plan['success_scope'] == 'planning'
    assert plan['planning_verdict'] == 'CONDITIONAL' and plan['deferred_checks']
    assert stats.results[0]['output'] == plan['output'] == ''
    assert not Path(plan['planned_output']).exists()
    return plan


def test_three_step_plan_preserves_suffix_type_and_intent(tmp_path, forbid_output_writes):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('image_resize', {'width': 12, 'height': 9}),
                     ('image_convert', {'format': 'JPEG'}), ('file_rename', {}))
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path / 'out')
    plan = assert_conditional(run_plan(source, steps, tmp_path / 'out'))
    artifacts = plan['artifacts'][1:]
    assert [artifact['suffix'] for artifact in artifacts] == ['.png', '.jpeg', '.jpeg']
    assert [artifact['producer_step'][0] for artifact in artifacts] == [1, 2, 3]
    assert all(artifact['state'] == 'PLANNED' and artifact['logical_type'] == 'image' for artifact in artifacts)
    assert any(fact['name'] == 'width' and fact['value'] == 12 and fact['provenance'] == 'CONFIGURATION_INTENT'
               for fact in artifacts[0]['facts'])
    assert not any(fact['name'] == 'dimensions' for artifact in artifacts for fact in artifact['facts'])
    assert attempts == [] and filesystem_snapshot(tmp_path) == before


@pytest.mark.parametrize('case', ['unknown', 'config', 'transition', 'disabled', 'disabled_shape', 'all_disabled'])
def test_static_preflight_and_disabled_steps(tmp_path, forbid_output_writes, case):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('file_rename', {}))
    if case == 'unknown':
        steps.add_step('unknown', {})
    elif case == 'config':
        steps.add_step('image_resize', {'width': 'bad'})
    elif case == 'transition':
        steps = workflow(('csv_filter', {'column': 'a'}), ('image_resize', {}))
    else:
        disabled = steps.add_step('unknown', {'width': 'bad'})
        disabled.enabled = False
        if case == 'disabled_shape':
            disabled.config = 'not a mapping'
        if case == 'all_disabled':
            steps.steps[0].enabled = False
    attempts = forbid_output_writes(tmp_path / 'out')
    stats = run_plan(source, steps, tmp_path / 'out')
    if case == 'disabled':
        assert assert_conditional(stats)['disabled_steps'] == [2]
    else:
        assert stats.planning_summary['verdict'] == 'REJECTED'
        assert stats.processed_files == 0 and stats.skipped_files == 1
        assert stats.planning_errors
        assert 'planned_output' not in stats.plan_results[0]
        assert all(check['outcome'] == 'BLOCKED' for check in stats.plan_results[0]['diagnostics'])
    assert attempts == [] and not (tmp_path / 'out').exists()


@pytest.mark.parametrize('case', ['missing', 'unreadable', 'oversized', 'corrupt_image', 'corrupt_pdf', 'corrupt_csv'])
def test_actual_source_failures_are_not_deferred(tmp_path, monkeypatch, forbid_output_writes, case):
    suffix = '.pdf' if case == 'corrupt_pdf' else '.csv' if case == 'corrupt_csv' else '.png'
    source = make_source(tmp_path / ('input' + suffix))
    operation = 'pdf_watermark' if suffix == '.pdf' else 'csv_filter' if suffix == '.csv' else 'image_convert'
    config = {'column': 'status'} if suffix == '.csv' else {}
    if case == 'missing':
        source.unlink()
    elif case.startswith('corrupt'):
        source.write_bytes(b'"unterminated\n' if suffix == '.csv' else b'corrupt')
    elif case == 'oversized':
        original = Path.stat
        def stat(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == source:
                return SimpleNamespace(st_size=MAX_FILE_SIZE + 1, st_mode=result.st_mode)
            return result
        monkeypatch.setattr(Path, 'stat', stat)
    else:
        original = Path.open
        def open_source(path, *args, **kwargs):
            if path == source:
                raise PermissionError('input read refused')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, 'open', open_source)
    attempts = forbid_output_writes(tmp_path / 'out')
    stats = run_plan(source, workflow((operation, config)), tmp_path / 'out')
    assert stats.failed_files == 1 and stats.processed_files == 0
    assert stats.plan_results[0]['planning_verdict'] == 'REJECTED'
    assert 'planned_output' not in stats.plan_results[0]
    assert attempts == []


@pytest.mark.parametrize('second_column,header,expected', [
    ('amount', 'status,amount', 'CONDITIONAL'),
    ('absent', 'status,amount', 'REJECTED'),
    ('amount', 'status,"amount, quoted"', 'CONDITIONAL'),
])
def test_csv_schema_proof_does_not_invent_intermediate_values(tmp_path, second_column, header, expected):
    source = tmp_path / 'input.csv'
    source.write_text(header + '\nactive,1\ninactive,2\n', encoding='utf-8')
    steps = workflow(('csv_filter', {'column': 'status', 'value': 'active'}),
                     ('file_rename', {}),
                     ('csv_filter', {'column': second_column, 'operator': '>', 'value': '0'}))
    stats = run_plan(source, steps, tmp_path / 'out')
    plan = stats.plan_results[0]
    assert plan['planning_verdict'] == expected
    first_facts = plan['artifacts'][1]['facts']
    assert any(fact['name'] == 'filtered_rows' and fact['value'] == 1 for fact in first_facts)
    if expected == 'CONDITIONAL':
        check = diagnostic(plan, 'csv_column')[0]
        assert check['outcome'] == ('DEFERRED' if 'quoted' in header else 'CHECKED')
        assert diagnostic(plan, 'csv_predicate', 'DEFERRED')
        assert not any(fact['name'] in {'filtered_rows', 'original_rows', 'dtypes', 'values'}
                       for fact in plan['artifacts'][-1]['facts'])
    else:
        assert 'absent' in stats.errors[0]['error']
        assert diagnostic(plan, 'upstream') == []
    assert not (tmp_path / 'out').exists()


def test_csv_zero_rows_and_invalid_numeric_operand(tmp_path):
    source = make_source(tmp_path / 'input.csv')
    steps = workflow(('csv_filter', {'column': 'status', 'value': 'absent'}))
    plan = assert_conditional(run_plan(source, steps, tmp_path / 'out'))
    assert any(fact['name'] == 'filtered_rows' and fact['value'] == 0 for fact in plan['artifacts'][1]['facts'])
    steps.add_step('csv_filter', {'column': 'value', 'operator': '>', 'value': 'not numeric'})
    assert run_plan(source, steps, tmp_path / 'out').plan_results[0]['planning_verdict'] == 'REJECTED'


@pytest.mark.parametrize('dry_support,plan_support', [(False, True), (True, False)])
def test_planning_capability_never_falls_back_to_execution(tmp_path, monkeypatch, dry_support, plan_support):
    source = make_source(tmp_path / 'input.png')
    calls = Mock(side_effect=AssertionError('Unsupported path invoked'))
    monkeypatch.setattr(FileRenameOperation, 'supports_dry_run', dry_support)
    monkeypatch.setattr(FileRenameOperation, 'supports_planning', plan_support)
    monkeypatch.setattr(FileRenameOperation, 'execute', calls)
    monkeypatch.setattr(FileRenameOperation, 'plan', calls)
    stats = run_plan(source, workflow(('file_rename', {}), ('image_filter', {})), tmp_path / 'out')
    assert stats.failed_files == 1 and stats.plan_results[0]['planning_verdict'] == 'UNSUPPORTED'
    assert diagnostic(stats.plan_results[0], 'upstream', 'BLOCKED')
    calls.assert_not_called()


def test_unknown_type_is_deferred_and_same_does_not_erase_it(tmp_path):
    descriptor = ArtifactDescriptor((1, 'original.png'), (1, 'synthetic'), 'PLANNED', 'UNKNOWN', None, '.png')
    plan = ImageConvertOperation().plan(descriptor, 2)
    assert any(check.check_id == 'input_type' and check.outcome == CheckOutcome.DEFERRED for check in plan.diagnostics)
    renamed = FileRenameOperation().plan(descriptor, 2)
    assert renamed.logical_type == 'UNKNOWN'
    assert not hasattr(descriptor, 'exists') and not hasattr(descriptor, 'is_file')


def test_naming_context_collisions_aliases_and_chained_rename(tmp_path):
    source = make_source(tmp_path / 'input.png')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'same.png').write_bytes(b'occupied')
    steps = workflow(('file_rename', {'pattern': 'same'}),
                     ('file_rename', {'pattern': '{original}_{counter}_{timestamp}'}))
    context = replace(PlanningContext.capture([str(source)], steps.to_dict(), '../../same', str(out)), timestamp='20260908_010203')
    results = []
    for _ in range(2):
        stats = run_plan(source, steps, out, planning_context=context)
        results.append(stats.plan_results[0])
    assert results[0] == results[1]
    assert Path(results[0]['artifacts'][1]['destination']).name == 'same_001.png'
    assert Path(results[0]['planned_output']).name == 'same_001_001_20260908_010203.png'
    assert (out / 'same.png').read_bytes() == b'occupied'
    assert list(out.iterdir()) == [out / 'same.png']
    steps = workflow(('file_rename', {'pattern': 'same'}), ('file_rename', {'pattern': 'same_001'}))
    stats = run_plan(source, steps, out)
    assert len({item['destination'] for item in stats.plan_results[0]['artifacts'][1:]}) == 2


@pytest.mark.parametrize('directory', ['', ' ', 'nul\x00path'])
def test_invalid_output_paths_are_not_normalized_into_success(tmp_path, directory):
    source = make_source(tmp_path / 'input.png')
    stats = run_plan(source, workflow(('file_rename', {})), directory)
    assert stats.planning_summary['verdict'] == 'REJECTED'


@pytest.mark.parametrize('dangling', [False, True])
def test_planned_suffix_link_is_rejected(tmp_path, dangling):
    source = make_source(tmp_path / 'input.png')
    out = tmp_path / 'out'
    out.mkdir()
    target = tmp_path / 'outside.jpeg'
    if not dangling:
        target.write_bytes(b'preserve')
    try:
        (out / 'input_processed.jpeg').symlink_to(target)
    except OSError as exc:
        pytest.skip(f'OS link creation unavailable: {exc}')
    stats = run_plan(source, workflow(('image_convert', {'format': 'JPEG'})), out)
    assert stats.plan_results[0]['planning_verdict'] == 'REJECTED'
    assert (out / 'input_processed.jpeg').is_symlink()
    assert not target.exists() if dangling else target.read_bytes() == b'preserve'


@pytest.mark.parametrize('after_allocation', [False, True])
def test_unrelated_intermediate_content_is_never_read(tmp_path, monkeypatch, after_allocation):
    source = make_source(tmp_path / 'input.png')
    out = tmp_path / 'out'
    out.mkdir()
    sentinel = out / 'input_processed.jpeg'
    original_read = Path.open
    original_allocate = OutputPathAllocator.allocate
    created = []
    if after_allocation:
        def allocate(allocator, stem, suffix):
            result = original_allocate(allocator, stem, suffix)
            if not created:
                # External actor simulation, deliberately outside application writing paths.
                with original_read(result, 'wb') as stream:
                    stream.write(b'unrelated bytes')
                created.append(result)
            return result
        monkeypatch.setattr(OutputPathAllocator, 'allocate', allocate)
    else:
        sentinel.write_bytes(b'unrelated bytes')
        created.append(sentinel)
    def open_path(path, *args, **kwargs):
        if path in created:
            raise AssertionError('Planned destination was mistaken for source content')
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', open_path)
    stats = run_plan(source, workflow(('image_convert', {'format': 'JPEG'}), ('image_filter', {})), out)
    assert stats.planning_summary['verdict'] == 'CONDITIONAL'
    assert diagnostic(stats.plan_results[0], 'intermediate_content', 'DEFERRED')
    with original_read(created[0], 'rb') as stream:
        assert stream.read() == b'unrelated bytes'


@pytest.fixture
def ocr_readiness(monkeypatch):
    image_ready = Mock(return_value=ocr_ops.OCRReadiness())
    pdf_ready = Mock(return_value=ocr_ops.OCRReadiness())
    monkeypatch.setattr(ocr_ops, 'get_image_ocr_readiness', image_ready)
    monkeypatch.setattr(ocr_ops, 'get_pdf_ocr_readiness', pdf_ready)
    monkeypatch.setattr(ocr_ops, 'get_pdf_native_readiness', lambda: ocr_ops.OCRReadiness())
    monkeypatch.setattr(PageObject, 'extract_text', Mock(side_effect=AssertionError('No native extraction in planning')))
    monkeypatch.setattr(ocr_ops, 'convert_from_path', Mock(side_effect=AssertionError('No rasterization')), raising=False)
    monkeypatch.setattr(ocr_ops, 'pytesseract', SimpleNamespace(image_to_string=Mock(side_effect=AssertionError('No recognition'))), raising=False)
    return image_ready, pdf_ready


@pytest.mark.parametrize('operation,suffix,mode,missing,verdict', [
    ('ocr_image', '.png', None, False, 'CONDITIONAL'),
    ('ocr_image', '.png', None, True, 'REJECTED'),
    ('ocr_pdf', '.pdf', 'native', True, 'CONDITIONAL'),
    ('ocr_pdf', '.pdf', 'ocr', True, 'REJECTED'),
    ('ocr_pdf', '.pdf', 'ocr', False, 'CONDITIONAL'),
    ('ocr_pdf', '.pdf', 'auto', True, 'CONDITIONAL'),
    ('ocr_batch', '.pdf', 'auto', True, 'CONDITIONAL'),
    ('ocr_batch', '.pdf', 'native', True, 'CONDITIONAL'),
    ('ocr_batch', '.png', None, True, 'REJECTED'),
    ('ocr_batch', '.png', None, False, 'CONDITIONAL'),
    ('ocr_batch', '.csv', None, False, 'REJECTED'),
])
def test_ocr_plans_preserve_mode_and_readiness_boundaries(tmp_path, ocr_readiness, operation, suffix, mode, missing, verdict):
    source = make_source(tmp_path / ('input' + suffix))
    for probe in ocr_readiness:
        probe.return_value = ocr_ops.OCRReadiness('unavailable requested language/tool' if missing else None)
    config = {'mode': mode} if mode else {}
    steps = workflow((operation, config), ('file_rename', {}))
    stats = run_plan(source, steps, tmp_path / 'out')
    plan = stats.plan_results[0]
    assert plan['planning_verdict'] == verdict
    if verdict == 'CONDITIONAL':
        assert plan['planned_output'].endswith('.txt')
        assert all(fact['name'] not in {'text', 'word_count'} for artifact in plan['artifacts'] for fact in artifact['facts'])
        if mode == 'auto':
            assert diagnostic(plan, 'auto_fallback', 'DEFERRED')
            ocr_readiness[1].assert_not_called()
    assert not (tmp_path / 'out').exists()


def test_aggregate_adapter_preserves_originals_and_partial_invalid_policy(tmp_path):
    valid = make_source(tmp_path / 'valid.pdf')
    invalid = tmp_path / 'invalid.pdf'
    invalid.write_bytes(b'bad PDF')
    stats = BatchProcessor(2).process_batch([str(valid), str(invalid)], workflow(('pdf_merge', {})), str(tmp_path / 'out'), dry_run=True)
    assert (stats.processed_files, stats.failed_files, stats.skipped_files) == (1, 1, 0)
    assert [plan['planning_verdict'] for plan in stats.plan_results] == ['CONDITIONAL', 'REJECTED']
    assert stats.planning_summary['verdict'] == 'REJECTED'
    assert stats.results[0]['output'] == '' and stats.results[0]['result']['planned_output'].endswith('.pdf')
    assert not (tmp_path / 'out').exists()


def test_mixed_batch_partition_and_original_counters(tmp_path, monkeypatch):
    first = make_source(tmp_path / 'first.png')
    absent = tmp_path / 'missing.png'
    third = make_source(tmp_path / 'unsupported.png')
    original = FileRenameOperation.plan
    def plan(operation, artifact, step):
        if artifact.name == third.name:
            return OperationPlan((PlanDiagnostic(step, operation.id, 'planning_support', 'structure',
                                                CheckOutcome.UNSUPPORTED, 'Synthetic unsupported capability'),))
        return original(operation, artifact, step)
    monkeypatch.setattr(FileRenameOperation, 'plan', plan)
    stats = BatchProcessor(2).process_batch([str(first), str(absent), str(third), str(first)],
                                           workflow(('file_rename', {})), str(tmp_path / 'out'), dry_run=True)
    assert (stats.processed_files, stats.failed_files, stats.skipped_files) == (2, 2, 0)
    assert [plan['planning_verdict'] for plan in stats.plan_results] == ['CONDITIONAL', 'REJECTED', 'UNSUPPORTED', 'CONDITIONAL']
    assert Path(stats.plan_results[3]['planned_output']).stem.endswith('_004')
    assert sum(stats.planning_summary[key] for key in ('CHECKED', 'CONDITIONAL', 'REJECTED', 'UNSUPPORTED', 'UNASSESSED')) == 4


def test_cancellation_keeps_partial_evidence_and_unstarted_inputs(tmp_path, monkeypatch, forbid_output_writes):
    source = make_source(tmp_path / 'input.png')
    entered, release = threading.Event(), threading.Event()
    original = ImageConvertOperation.plan
    def plan(operation, artifact, step):
        result = original(operation, artifact, step)
        entered.set()
        assert release.wait(5), 'Test release missing'
        return result
    monkeypatch.setattr(ImageConvertOperation, 'plan', plan)
    processor = BatchProcessor(2)
    attempts = forbid_output_writes(tmp_path / 'out')
    worker = threading.Thread(target=processor.process_batch,
                              args=([str(source), str(source)], workflow(('image_convert', {}), ('file_rename', {})), str(tmp_path / 'out')),
                              kwargs={'dry_run': True})
    worker.start()
    try:
        assert entered.wait(5)
        processor.stop()
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    stats = processor.stats
    assert stats.execution_state == 'CANCELLED' and stats.stopped
    assert [plan['assessment_state'] for plan in stats.plan_results] == ['PARTIAL', 'NOT_STARTED']
    assert stats.skipped_files == 2 and stats.failed_files == stats.processed_files == 0
    assert all('planned_output' not in plan for plan in stats.plan_results)
    assert attempts == []


def test_unexpected_assessment_failure_is_incomplete(tmp_path, monkeypatch):
    source = make_source(tmp_path / 'input.png')
    monkeypatch.setattr(FileRenameOperation, 'plan', Mock(side_effect=RuntimeError('injected assessment failure')))
    stats = run_plan(source, workflow(('file_rename', {})), tmp_path / 'out')
    assert stats.execution_state == 'INCOMPLETE'
    assert stats.plan_results[0]['assessment_state'] == 'PARTIAL'
    assert stats.plan_results[0]['interrupted']
    assert not stats.plan_results[0]['success'] and stats.skipped_files == 1
    assert diagnostic(stats.plan_results[0], 'assessment_exception', 'BLOCKED')


def test_snapshot_and_processor_reuse_do_not_share_state(tmp_path):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('file_rename', {'pattern': '{original}_{timestamp}', 'nested': {'items': [1, 2]}}))
    context = PlanningContext.capture([str(source)], steps.to_dict(), '{original}', str(tmp_path / 'out'))
    processor = BatchProcessor(2)
    first = processor.process_batch([], Workflow('ignored'), 'ignored', dry_run=True, planning_context=context)
    before = copy.deepcopy(first.to_dict())
    steps.steps[0].config['nested']['items'].append(3)
    decoded = context.workflow_dict()
    decoded['steps'][0]['config']['pattern'] = 'modified'
    with pytest.raises(FrozenInstanceError):
        context.timestamp = 'changed'
    with pytest.raises(AttributeError):
        first.planning_context = None
    second = processor.process_batch([], Workflow('ignored'), 'ignored', dry_run=True, planning_context=context)
    assert first.to_dict() == before
    assert first.results[0]['result']['planned_output'] == second.results[0]['result']['planned_output']
    assert context.workflow_dict()['steps'][0]['config']['nested']['items'] == [1, 2]
    fresh = processor.process_batch([str(source)], steps, str(tmp_path / 'out'), dry_run=True)
    assert fresh.planning_context.run_id != context.run_id
    assert first.to_dict() == before
    assert not (tmp_path / 'out').exists()


def logs_panel():
    panel = LogsPanel.__new__(LogsPanel)
    panel.main_window = SimpleNamespace(set_status=Mock(), run_panel=SimpleNamespace(output_dir=Mock()))
    for name in ('results_tree', 'errors_tree', 'summary_text', 'notebook', 'total_card', 'success_card', 'failed_card', 'duration_card'):
        setattr(panel, name, Mock())
    for name in ('total_card', 'success_card', 'failed_card', 'duration_card'):
        getattr(panel, name).winfo_children.return_value = []
    panel.results_tree.get_children.return_value = []
    panel.errors_tree.get_children.return_value = []
    panel._open_file = Mock()
    panel._open_folder = Mock()
    return panel


def test_logs_never_claim_or_open_generated_plans(tmp_path):
    source = make_source(tmp_path / 'input.png')
    stats = run_plan(source, workflow(('image_convert', {}), ('file_rename', {})), tmp_path / 'out')
    panel = logs_panel()
    panel.show_stats(stats)
    assert panel.output_files == {}
    assert panel.results_tree.insert.call_args.kwargs['values'][1] == 'Conditional plan'
    text = '\n'.join(call.args[1] for call in panel.summary_text.insert.call_args_list)
    assert 'CONDITIONAL: 1' in text and 'No files were generated' in text
    assert 'Success rate' not in text and 'Successfully processed' not in text
    # Even an occupied path in legacy fallback state must not be opened.
    panel.results_tree.selection.return_value = ['selected']
    for route in ('_open_selected_file', '_open_containing_folder', '_copy_file_path'):
        getattr(panel, route)()
    panel._open_file.assert_not_called()
    panel._open_folder.assert_not_called()
    panel.main_window.run_panel.output_dir.get.assert_not_called()


def test_run_panel_reports_conditional_counts_without_celebration(tmp_path, monkeypatch):
    source = make_source(tmp_path / 'input.png')
    stats = run_plan(source, workflow(('file_rename', {})), tmp_path / 'out')
    panel = RunPanel.__new__(RunPanel)
    for name in ('start_button', 'pause_button', 'stop_button', 'status_label', 'processor', '_log', '_show_confetti'):
        setattr(panel, name, Mock())
    dialog = Mock()
    monkeypatch.setattr(run_panel.messagebox, 'showinfo', dialog)
    panel._processing_complete(stats, str(tmp_path / 'out'), True)
    assert '1 conditional plans' in dialog.call_args.args[1]
    assert any('deferred:' in call.args[0] for call in panel._log.call_args_list)
    panel._show_confetti.assert_not_called()
    panel.processor.generate_report.assert_not_called()


@pytest.mark.parametrize('operation,suffix,config', [
    ('file_rename', '.png', {}), ('image_resize', '.png', {}), ('image_convert', '.png', {}),
    ('image_filter', '.png', {}), ('pdf_watermark', '.pdf', {}),
    ('csv_filter', '.csv', {'column': 'status'}), ('ocr_image', '.png', {}),
    ('ocr_pdf', '.pdf', {'mode': 'auto'}), ('ocr_batch', '.png', {}), ('ocr_batch', '.pdf', {}),
    ('pdf_merge', '.pdf', {}),
])
def test_planners_attempt_no_global_temps_or_transformations(tmp_path, monkeypatch, forbid_output_writes, ocr_readiness, operation, suffix, config):
    source = make_source(tmp_path / ('input' + suffix))
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path / 'out')
    forbidden = Mock(side_effect=AssertionError('Forbidden temp/transformation/write attempt'))
    for name in ('NamedTemporaryFile', 'TemporaryFile', 'mkstemp', 'mkdtemp'):
        monkeypatch.setattr(tempfile, name, forbidden)
    for name in ('save', 'resize', 'thumbnail', 'filter'):
        monkeypatch.setattr(Image.Image, name, forbidden)
    monkeypatch.setattr(PdfWriter, 'write', forbidden)
    monkeypatch.setattr(ocr_ops.subprocess, 'run', forbidden)
    stats = run_plan(source, workflow((operation, config)), tmp_path / 'out')
    assert stats.planning_summary['verdict'] == 'CONDITIONAL'
    forbidden.assert_not_called()
    assert attempts == [] and filesystem_snapshot(tmp_path) == before


@pytest.mark.parametrize('change', ['delete', 'corrupt', 'destination', 'capability'])
def test_normal_run_revalidates_after_planning(tmp_path, monkeypatch, ocr_readiness, change):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('ocr_image' if change == 'capability' else 'image_convert', {}))
    out = tmp_path / 'out'
    plan = assert_conditional(run_plan(source, steps, out))
    if change == 'delete':
        source.unlink()
    elif change == 'corrupt':
        source.write_bytes(b'corrupt')
    elif change == 'destination':
        out.mkdir()
        Path(plan['planned_output']).write_bytes(b'new owner')
    else:
        ocr_readiness[0].return_value = ocr_ops.OCRReadiness('capability disappeared')
    stats = BatchProcessor(1).process_batch([str(source)], steps, str(out))
    if change == 'destination':
        assert stats.failed_files == 0 and stats.processed_files == 1
        assert stats.results[0]['output'] != plan['planned_output']
        assert Path(plan['planned_output']).read_bytes() == b'new owner'
        with Image.open(stats.results[0]['output']) as image:
            assert image.size == (16, 16)
    else:
        assert stats.failed_files == 1 and not stats.results
        assert not Path(plan['planned_output']).exists()


@pytest.mark.parametrize('aggregate', [False, True])
def test_empty_plans_keep_validation_and_lifecycle_distinct(tmp_path, aggregate, forbid_output_writes):
    attempts = forbid_output_writes(tmp_path / 'out')
    stats = BatchProcessor(2).process_batch([], workflow(('pdf_merge' if aggregate else 'file_rename', {})),
                                           str(tmp_path / 'out'), dry_run=True)
    assert stats.execution_state == 'COMPLETED'
    assert stats.planning_summary['verdict'] == ('REJECTED' if aggregate else 'EMPTY')
    assert stats.failed_files == int(aggregate)
    assert stats.plan_results == [] and stats.processed_files == stats.skipped_files == 0
    assert attempts == [] and not (tmp_path / 'out').exists()


def test_generated_any_type_and_same_are_not_validation_passes(tmp_path, monkeypatch):
    class UnknownProducer(FileRenameOperation):
        id, output_type = 'unknown_producer', 'any'
    source = make_source(tmp_path / 'input.png')
    processor = BatchProcessor(2)
    processor.operation_registry.operations['unknown_producer'] = UnknownProducer
    monkeypatch.setattr(UnknownProducer, 'execute', Mock(side_effect=AssertionError('execution forbidden')))
    stats = processor.process_batch([str(source)], workflow(('unknown_producer', {}), ('file_rename', {}),
                                   ('image_convert', {'format': 'JPEG'})), str(tmp_path / 'out'), dry_run=True)
    plan = assert_conditional(stats)
    assert [item['logical_type'] for item in plan['artifacts'][1:]] == ['UNKNOWN', 'UNKNOWN', 'image']
    assert any(item['step_index'] == 3 for item in diagnostic(plan, 'input_type', 'DEFERRED'))
    UnknownProducer.execute.assert_not_called()


def test_actual_csv_invalid_regex_is_a_demonstrated_failure(tmp_path):
    source = tmp_path / 'input.csv'
    source.write_text('name\nalpha\n', encoding='utf-8')
    stats = run_plan(source, workflow(('csv_filter', {'column': 'name', 'operator': 'contains', 'value': '['})),
                     tmp_path / 'out')
    assert stats.planning_summary['verdict'] == 'REJECTED'
    assert stats.execution_state == 'COMPLETED' and stats.failed_files == 1
    assert diagnostic(stats.plan_results[0], 'csv_predicate', 'FAILED')


def test_post_plan_valid_source_change_is_processed_again(tmp_path):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('image_convert', {'format': 'JPEG'}))
    before = run_plan(source, steps, tmp_path / 'out').to_dict()
    Image.new('RGB', (17, 11), 'blue').save(source)
    stats = BatchProcessor(2).process_batch([str(source)], steps, str(tmp_path / 'out'))
    assert stats.processed_files == 1 and stats.failed_files == 0
    with Image.open(stats.results[0]['output']) as generated:
        assert generated.size == (17, 11)
    assert before['dry_run'] and before['results'][0]['output'] == ''


def test_format_intent_survives_suffix_preserving_steps(tmp_path):
    source = make_source(tmp_path / 'input.png')
    plan = assert_conditional(run_plan(source, workflow(('image_convert', {'format': 'JPEG'}),
        ('image_resize', {}), ('image_filter', {}), ('file_rename', {})), tmp_path / 'out'))
    assert all(artifact['logical_format'] == 'JPEG' and artifact['suffix'] == '.jpeg'
               for artifact in plan['artifacts'][1:])



def test_equal_invalid_steps_keep_original_diagnostic_indices(tmp_path):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('image_resize', {'width': 'invalid'}), ('image_resize', {'width': 'invalid'}))
    stats = run_plan(source, steps, tmp_path / 'out')
    assert [item['step_index'] for item in stats.planning_errors] == [1, 2]
    assert stats.planning_summary['verdict'] == 'REJECTED'


@pytest.mark.parametrize('entrypoint', ['batch', 'single'])
def test_invalid_destination_never_constructs_allocator(tmp_path, monkeypatch, entrypoint):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('file_rename', {}))
    constructor = Mock(side_effect=AssertionError('Allocator must follow valid preflight'))
    monkeypatch.setattr('core.planning.OutputPathAllocator', constructor)
    if entrypoint == 'batch':
        stats = run_plan(source, steps, 'nul\x00path')
        assert stats.planning_summary['verdict'] == 'REJECTED'
        assert stats.execution_state == 'COMPLETED'
    else:
        result = process_single_file(str(source), steps.to_dict(), 'nul\x00path', '{original}', dry_run=True)
        assert result['planning_verdict'] == 'REJECTED'
    constructor.assert_not_called()


@pytest.mark.parametrize('malformed', [{}, {'name': 'bad', 'steps': [None]}, {'name': 'bad', 'steps': [], 'metadata': {'value': object()}}])
def test_direct_dry_run_malformed_workflow_returns_structured_failure(tmp_path, malformed, forbid_output_writes):
    source = make_source(tmp_path / 'input.png')
    before = filesystem_snapshot(tmp_path)
    attempts = forbid_output_writes(tmp_path / 'out')
    result = process_single_file(str(source), malformed, str(tmp_path / 'out'), '{original}', dry_run=True)
    assert not result['success'] and result['planning_verdict'] == 'REJECTED'
    assert result['output'] == '' and 'planned_output' not in result
    assert diagnostic(result, 'structure', 'FAILED')
    assert attempts == [] and filesystem_snapshot(tmp_path) == before


def test_disabled_steps_preserve_human_and_structured_error_indices(tmp_path):
    source = make_source(tmp_path / 'input.png')
    steps = workflow(('file_rename', {}), ('image_resize', {'width': 'invalid'}))
    steps.steps[0].enabled = False
    stats = run_plan(source, steps, tmp_path / 'out')
    assert stats.planning_errors[0]['step_index'] == 2
    assert 'step 2' in stats.planning_errors[0]['reason']


def test_rejected_plans_count_as_assessed_in_both_ui_consumers(tmp_path, monkeypatch):
    source = tmp_path / 'bad.png'
    source.write_bytes(b'not an image')
    stats = run_plan(source, workflow(('image_convert', {})), tmp_path / 'out')
    assert stats.processed_files == 0 and stats.assessed_plans == 1
    panel = logs_panel()
    panel._update_stat_card = Mock()
    panel.show_stats(stats)
    panel._update_stat_card.assert_any_call(panel.success_card, '1')
    run = RunPanel.__new__(RunPanel)
    for name in ('start_button', 'pause_button', 'stop_button', 'status_label', 'progress_bar', 'processor'):
        setattr(run, name, Mock())
    run._log = Mock()
    run._show_confetti = Mock()
    run.main_window = Mock()
    show = Mock()
    monkeypatch.setattr(run_panel.messagebox, 'showinfo', show)
    run._processing_complete(stats, False, str(tmp_path / 'out'))
    assert any('Assessed plans: 1' in call.args[0] and 'rejected: 1' in call.args[0]
               for call in run._log.call_args_list)
    assert 'Assessed plans: 1' in show.call_args.args[1]
    run._show_confetti.assert_not_called()
