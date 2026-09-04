# Operations reference

`core/operations/registry.py` is authoritative. It registers nine per-file operations and one aggregate operation. Extension classification maps images to `image`, PDF to `pdf`, CSV to `csv`, Excel extensions to `spreadsheet`, and TXT/JSON/XML to `text`.

| Operation ID | Class | Accepted input | Output | Configuration | Mode | Dry-run behavior | Dependencies | Principal failure modes |
|---|---|---|---|---|---|---|---|---|
| `image_resize` | `ImageResizeOperation` | `image`: jpg, jpeg, png, gif, bmp, webp, tiff, tif | Image, input suffix | `width:int=800`, `height:int=600`, `maintain_aspect:bool=true`, `quality:int=95` | File | Returns planned path; does not open or write the image | Pillow | Unreadable image, unsupported encoder/mode, write error |
| `image_convert` | `ImageConvertOperation` | `image` | PNG, JPEG, WEBP, BMP, or TIFF | `format` choice, default `PNG` | File | Returns the path with target-format suffix; no write | Pillow | Unreadable image, unsupported conversion/encoder, write error |
| `image_filter` | `ImageFilterOperation` | `image` | Image, input suffix | `filter` choice; optional `brightness:float`, `contrast:float` | File | Returns planned path; no image write | Pillow | Unreadable image, invalid numeric value, unsupported save mode, write error |
| `pdf_watermark` | `PDFWatermarkOperation` | `pdf` | PDF | `text:str=CONFIDENTIAL` | File | Returns planned path; no PDF write | pypdf, reportlab | Invalid/encrypted PDF, page merge failure, write error |
| `csv_filter` | `CSVFilterOperation` | `csv` | CSV | `column:str`, `operator` in `==`, `!=`, `>`, `<`, `contains`; `value:str` | File | Reads and filters the CSV, returns counts, but does not write | pandas | CSV parse/encoding error, nonnumeric comparison value, write error |
| `file_rename` | `FileRenameOperation` | `any` registry-classified input | Same suffix | `pattern:str={original}_{counter}` | File | Returns sanitized target path; no copy | Standard library | Missing source, invalid counter, copy/permission error |
| `ocr_image` | `OCRImageOperation` | `image` | UTF-8 TXT | `language:str=eng`; accepted but currently unapplied: `page_segmentation_mode:int=3`, `grayscale:bool=false`, `threshold:bool=false` | File | Requires detected Tesseract, then returns TXT path without extraction/write | Pillow, pytesseract, Tesseract executable, requested language data | Missing executable/package/language, unreadable image, OCR or write error |
| `ocr_pdf` | `OCRPDFOperation` | `pdf` | UTF-8 TXT | `mode` in `auto`, `native`, `ocr`; `language:str=eng`, `dpi:int=200` | File | Returns TXT path without opening or writing | pypdf; OCR modes also pytesseract, Tesseract, pdf2image, Poppler | Invalid/encrypted PDF, missing OCR tool, rasterization/OCR/language/write error |
| `ocr_batch` | `OCRBatchOperation` | Declared `any`; runtime delegates PDF or image | One UTF-8 TXT per input | `language:str=eng`; accepted but currently unapplied: `combine_output`, `combined_filename` | File | Delegates to image/PDF dry run; no text output | OCR image dependencies; PDF path may also require pdf2image and Poppler | Non-image/non-PDF input, missing OCR tool, delegated extraction failure |
| `pdf_merge` | `PDFAggregateMergeOperation` | `pdf` | One PDF | `output_filename:str=merged_output.pdf` | Aggregate | Initializes no writer, validates/queues inputs, and returns planned final path without writing | pypdf | Invalid/encrypted PDF, no valid PDFs, not initialized, final write error |

## Image filter choices

The registered values are `BLUR`, `SHARPEN`, `SMOOTH`, `EDGE_ENHANCE`, `EMBOSS`, `CONTOUR`, and `GRAYSCALE`. Brightness and contrast are applied only when the keys are present in the operation configuration.

## CSV behavior

If `column` is empty or is not present in the parsed CSV, the operation succeeds with the original rows unchanged. Numeric `>` and `<` comparisons convert the configured value to `float`; data-column comparison rules are then pandas rules. `contains` uses string conversion and treats missing values as nonmatches.

## OCR behavior

`native` PDF mode uses pypdf text extraction and does not require Tesseract. `auto` switches to OCR when stripped native text is shorter than 50 characters. Workflow compilation therefore requires OCR capabilities for both `auto` and `ocr` modes even if a particular auto-mode PDF might contain native text.

The current image OCR implementation uses only `language`; its other exposed preprocessing fields are not applied. The current batch OCR implementation creates per-file outputs; `combine_output` and `combined_filename` are not applied. These are documented limitations, not promised features.

## Result contract

Every operation lifecycle method returns `OperationResult`: `success`, `message`, optional `output_path`, optional `error`, and a metadata mapping. The processor treats a successful per-file operation without an output path as a failed contract.
