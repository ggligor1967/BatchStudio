# 🚀 BatchStudio Quick Start Guide

Get up and running with BatchStudio in 5 minutes!

## 📦 Installation (2 minutes)

```bash
# 1. Navigate to BatchStudio directory
cd BatchStudio

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify installation (optional)
python test_installation.py
```

That's it! BatchStudio is ready to use.

## 🎯 Your First Batch (3 minutes)

### Example: Resize 100 Photos

**Step 1: Add Files** (30 seconds)
1. Launch BatchStudio: `python main.py`
2. Go to "📁 Input Files" tab
3. Click "Add Folder" → Select your photos folder
4. See preview and stats

**Step 2: Build Workflow** (1 minute)
1. Go to "🔧 Workflow" tab
2. Double-click "📋 Image Resizer" template
3. Or manually:
   - Select "🔧 Image Resize" from operations
   - Click "➕ Add to Workflow"
   - Configure: Width 1920, Height 1080
   - Check "Maintain Aspect Ratio"

**Step 3: Run** (30 seconds)
1. Go to "▶️ Run" tab
2. Set output directory (or use default)
3. Click "▶️ Start Processing"
4. Watch progress bar!

**Step 4: View Results** (1 minute)
1. Go to "📊 Logs" tab
2. Check statistics
3. View HTML report
4. Done! 🎉

## 💡 Quick Tips

### Keyboard Shortcuts
- `Ctrl+N`: New workflow
- `Ctrl+O`: Open workflow
- `Ctrl+S`: Save workflow
- `Ctrl+Shift+D`: Developer console (Easter egg!)

### Best Practices
- **Start small**: Test with 10-20 files first
- **Use dry run**: Preview changes before running
- **Save workflows**: Reuse your favorite setups
- **Check logs**: Always review results

## 📚 Common Workflows

### 1. Photo Optimizer for Web
```
Operations:
1. Resize → 1200x800
2. Sharpen filter
3. Convert to WEBP
Result: Smaller, faster-loading images
```

### 2. PDF Watermark
```
Operations:
1. PDF Watermark → "CONFIDENTIAL"
Result: Protected documents
```

### 3. Batch Rename
```
Operations:
1. File Rename → "IMG_{counter}"
Result: photo_001.jpg, photo_002.jpg, ...
```

### 4. Image Format Convert
```
Operations:
1. Convert → PNG
Result: All images as PNG
```

## 🔧 Troubleshooting

### "Module not found"
```bash
pip install -r requirements.txt
```

### Slow processing
- Increase workers in Run tab (try 8)
- Use SSD instead of HDD
- Close other applications

### Out of memory
- Reduce parallel workers
- Process fewer files at once
- Close preview images

## 📖 Next Steps

1. **Explore templates**: Try all pre-built workflows
2. **Create custom workflows**: Chain multiple operations
3. **Save your workflows**: Export as JSON for reuse
4. **Check README.md**: For detailed documentation
5. **Experiment**: BatchStudio is designed to be explored!

## 🎨 Fun Features

- 🎉 **Confetti animation** on completion
- 💬 **Motivational quotes** during processing
- 🌙 **Dark mode** in View menu
- 🎮 **Developer console** (Ctrl+Shift+D)

## 📞 Need Help?

- **Documentation**: README.md
- **Architecture**: ARCHITECTURE.txt
- **Test**: `python test_installation.py`

---

**Happy batch processing! ✨**

Made with ❤️ by BatchStudio Team
