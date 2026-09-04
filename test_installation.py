#!/usr/bin/env python3
"""
BatchStudio Installation Test
Verifies that all components work correctly.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test external dependencies
        import PIL
        import pandas
        import reportlab
        from pypdf import PdfReader
        print("   [OK] External dependencies OK")
        
        # Test internal modules
        from core import BatchProcessor, Workflow, OperationRegistry
        from ui import MainWindow
        print("   [OK] Internal modules OK")
        
        return True
    except ImportError as e:
        print(f"   [FAIL] Import failed: {e}")
        return False


def test_operations():
    """Test that operations can be instantiated."""
    print("\nTesting operations...")
    
    try:
        from core import OperationRegistry
        
        registry = OperationRegistry()
        operations = registry.list_operations()
        
        print(f"   Found {len(operations)} operations:")
        for op in operations:
            print(f"      - {op['name']}")
        
        # Test creating an operation
        op = registry.get_operation('image_resize', {'width': 800, 'height': 600})
        if op:
            print("   [OK] Operations working correctly")
            return True
        else:
            print("   [FAIL] Failed to create operation")
            return False
            
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def test_workflow():
    """Test workflow creation and management."""
    print("\nTesting workflows...")
    
    try:
        from core import Workflow, WorkflowTemplates
        
        # Test creating a workflow
        workflow = Workflow("Test Workflow", "Testing")
        workflow.add_step('image_resize', {'width': 1920, 'height': 1080})
        
        print(f"   Created workflow with {len(workflow.steps)} step(s)")
        
        # Test templates
        templates = WorkflowTemplates.list_templates()
        print(f"   Found {len(templates)} templates:")
        for template in templates:
            print(f"      - {template['name']}")
        
        print("   [OK] Workflows working correctly")
        return True
        
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def test_processor():
    """Test batch processor initialization."""
    print("\nTesting processor...")
    
    try:
        from core import BatchProcessor
        
        processor = BatchProcessor(max_workers=4)
        print(f"   Initialized processor with {processor.max_workers} workers")
        print("   [OK] Processor working correctly")
        return True
        
    except Exception as e:
        print(f"   [FAIL] Error: {e}")
        return False


def main():
    """Run all tests."""
    print("""
    ================================================================
                  BATCHSTUDIO INSTALLATION TEST
    ================================================================
    """)
    
    tests = [
        ("Imports", test_imports),
        ("Operations", test_operations),
        ("Workflows", test_workflow),
        ("Processor", test_processor)
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"   {name}: {status}")
    
    print("="*60)
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("""
    ================================================================
                       ALL TESTS PASSED!
    ================================================================
    
    BatchStudio is ready to use!
    
    Run the application with:
        python main.py
        """)
        return 0
    else:
        print("""
    WARNING: Some tests failed. Please check the errors above.
    
    Try running setup again:
        python setup.py
        """)
        return 1


if __name__ == "__main__":
    sys.exit(main())
