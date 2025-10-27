# 🐛 Troubleshooting

### Common Issues

**Files not appearing after scan:**
- Verify the repository directory path
- Ensure files have `.fits`, `.fit`, or `.fts` extensions
- Check log tab for processing errors

**External viewer not working:**
- Verify the viewer application path
- Ensure the application accepts FITS files as arguments
- Test the viewer independently

**Slow performance:**
- Large repositories may take time to process
- Use progress dialogs to monitor operations
- Consider processing in smaller batches

**Database corruption:**
- Delete `astrofiler.db` to reset the database
- Reload your repository to rebuild the catalog

**Duplicate files not detected:**
- Ensure files have been processed with the latest version
- Use "Refresh Duplicates" to update the duplicate list
- Check that file hashes were calculated during repository loading

### Log Analysis

The Log tab provides detailed information about:
- File processing status
- Error messages and stack traces
- Performance metrics
- Database operations