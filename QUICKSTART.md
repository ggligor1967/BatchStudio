# BatchStudio quick start

This path uses an image resize because it needs no optional OCR runtime.

## 1. Install from source

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install .
```

## 2. Start the application

```powershell
batchstudio-gui
```

From an uninstalled source checkout, `python main.py` is equivalent.

## 3. Process one image

1. Open **Input Files**, select **Add Files**, and choose a PNG or JPEG image.
2. Open **Workflow**, select **Resize Image**, and add it to the workflow.
3. Set `width` and `height`; leave `maintain_aspect` enabled if the image must retain its proportions.
4. Open **Run** and select an output directory.
5. Enable **Dry Run**, start processing, and confirm the planned result in **Logs**.
6. Disable **Dry Run** and start processing again.
7. Confirm the successful result and open the output directory from **Logs**.

The created image uses the run-panel naming pattern and a safe, collision-resistant destination. Existing files are not overwritten by the output allocator.

## If the run does not start

- Confirm that the selected file still exists and has a supported extension.
- Confirm that the workflow contains at least one enabled step compatible with the input.
- Confirm that the output directory is writable.
- For OCR workflows, follow [OCR setup](docs/OCR.md).

Continue with the [User guide](docs/USER_GUIDE.md) or the complete [Operations reference](docs/OPERATIONS.md).
