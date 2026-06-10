# Vitrine file storage

Uploaded assets are stored here by category:

| Folder | Purpose | Max size |
|--------|---------|----------|
| `listings/` | Product covers & screenshots | 10 MB |
| `chats/` | Chat images & PDFs | 4 MB |
| `avatars/` | User profile images | 2 MB |
| `documents/` | README uploads, specs | 10 MB |

Files are served at `/files/<bucket>/<user_id>/<filename>`.

**Note:** Uploaded content is gitignored; only this README and `.gitkeep` files are tracked.
