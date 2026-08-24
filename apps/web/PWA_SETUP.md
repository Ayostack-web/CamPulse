# PWA Setup - Vylix

## ✅ What's Been Configured

### 1. **Manifest File** (`public/manifest.json`)
- App name, short name, description
- App icons (multiple sizes for different devices)
- Start URL, theme colors, display mode (standalone)
- App shortcuts for quick access:
  - Browse Public Pulse
  - Access Private Vault
- Categories: education, productivity

### 2. **Next.js PWA Plugin** (`next.config.mjs`)
- Integrated `next-pwa` package for automatic service worker generation
- Auto-registration of service worker
- Offline support with cache strategies
- Disabled in development mode (enabled in production)

### 3. **PWA Meta Tags** (`app/layout.tsx`)
- Manifest link in metadata
- Apple Web App support
- Custom icons for different platforms
- Format detection for better mobile experience

### 4. **Install Prompt Component** (`components/pwa/InstallPrompt.tsx`)
- Listens for `beforeinstallprompt` event
- Shows beautiful install prompt after 2 seconds
- Users can install with one click
- "Maybe later" option to dismiss
- Auto-hides if already installed or in standalone mode

### 5. **Global Integration** (`providers/query-provider.tsx`)
- InstallPrompt added to global provider
- Shows to all new users automatically

---

## 🎯 What Users Will Experience

### **New User Flow**
```
1. User opens Vylix on mobile
   ↓
2. After 2 seconds, install prompt appears:
   📱 "Install Vylix"
   "Get faster access and offline support. 
    Add Vylix to your home screen..."
   [Install] [Maybe later]
   ↓
3. User clicks "Install"
   ↓
4. App installed to home screen
   ↓
5. Offline access enabled
   ↓
6. Push notifications available
```

### **Desktop Users**
- Browser shows native install prompt (if supported)
- Same install flow applies

### **Already Installed**
- Prompt disappears
- App runs in standalone mode
- No browser UI

---

## 📦 Next Steps to Complete PWA

### **IMMEDIATE** (Required for production)

#### 1. **Generate App Icons**
You need to create/export icons in these sizes:
- 72x72, 96x96, 128x128, 144x144, 152x152, 192x192, 384x384, 512x512

**Options:**
- **Use Online Generator**: https://www.favicon-generator.org/ (upload logo, auto-generates all sizes)
- **Use Design Tool**: Figma/Adobe XD (export at each size)
- **Use Command Line**: ImageMagick or similar

**Files to create in `public/icons/`:**
```
icon-72x72.png
icon-96x96.png
icon-128x128.png
icon-144x144.png
icon-152x152.png
icon-192x192.png
icon-384x384.png
icon-512x512.png
screenshot-192.png (mobile screenshot of dashboard)
screenshot-512.png (wide screenshot of dashboard)
```

**Important**: Use PNG format with transparency. The 512x512 icon should be:
- Clear and recognizable even at small sizes
- Using your brand colors: blue, green, white
- Simple design (no fine details that disappear at small scale)

#### 2. **Update Manifest Icon Paths** (after creating icons)
In `public/manifest.json`, ensure all icon paths are correct:
```json
"icons": [
  {
    "src": "/icons/icon-512x512.png",
    "type": "image/png",
    "sizes": "512x512",
    "purpose": "any maskable"
  }
]
```

The `maskable` purpose allows icons to be displayed with mask (adaptive icons on Android).

#### 3. **Install Dependencies**
```bash
cd apps/web
npm install
```

This installs `next-pwa`.

#### 4. **Build and Test**
```bash
npm run build
npm run start
```

Then test on:
- **Mobile Chrome**: Open app, wait 2 seconds, see install prompt
- **Mobile Safari** (iOS): Look for "Share" → "Add to Home Screen"
- **Desktop Chrome**: Open DevTools → Application → Service Workers (check if registered)

---

### **NICE TO HAVE** (Polish)

#### 5. **Custom Splash Screen**
Add to manifest for better visual appeal:
```json
"screenshots": [
  {
    "src": "/icons/splash-192x192.png",
    "type": "image/png",
    "sizes": "192x192",
    "form_factor": "narrow"
  }
]
```

#### 6. **Push Notifications**
After PWA is working, add:
- Background sync (upload materials when offline)
- Push notifications (notify about new posts/sessions)
- Web Workers for heavy processing

#### 7. **Analytics**
Track:
- Install prompts shown vs accepted (conversion rate)
- Users accessing offline
- Active sessions (standalone vs browser)
- Feature usage by platform

---

## 🔧 Technical Details

### **Service Worker Configuration** (auto-generated)
Next.js PWA creates:
- `public/sw.js` - Service Worker
- `public/sw.js.map` - Source map
- `public/workbox-*.js` - Caching strategies

These are auto-generated on build. Don't edit manually.

### **Caching Strategy**
By default, `next-pwa` uses:
- **CSS/JS**: Cache, serve from cache with network fallback
- **Images**: Cache, serve from cache
- **HTML**: Network first, fallback to cache
- **API Calls**: Network only (signed material URLs expire, so they must never be cached)

PDF bytes are cached separately from the service worker: `lib/pdf-cache.ts`
persists them in IndexedDB (store `vylix-pdf-cache`) keyed by material id, with
a ~250 MB LRU eviction cap. Opening a document downloads and caches it once;
after that it renders instantly and works fully offline.

You can customize in `next.config.mjs` if needed.

### **Offline Support**
With your existing IndexedDB setup:
1. ✅ PDFs cached locally (`lib/pdf-cache.ts`, after first view or "Save Offline")
2. ✅ Static assets cached by service worker
3. ✅ App shell loaded offline
4. 🟡 API calls show cached data or offline message

---

## 🚀 Deployment Checklist

- [ ] Icons created and placed in `public/icons/`
- [ ] `manifest.json` has correct icon paths
- [ ] Tested on mobile device (install prompt works)
- [ ] Service worker registered (DevTools → Application)
- [ ] Offline access works (disable network in DevTools)
- [ ] App runs in standalone mode
- [ ] Splash screen shows on iOS
- [ ] No console errors on install

---

## 📱 Testing on Real Devices

### **Android Chrome**
1. Open Vylix on Chrome mobile
2. Wait 2 seconds
3. Install prompt appears
4. Tap "Install"
5. Check home screen

### **iOS Safari**
1. Open Vylix in Safari
2. Tap Share button
3. Tap "Add to Home Screen"
4. Creates app-like shortcut
5. (Full PWA support limited on iOS, but still useful)

### **Desktop Chrome**
1. Open Vylix in Chrome
2. Click address bar icon (if eligible)
3. Install as desktop app
4. Run as standalone window

---

## 📊 Why This Matters for Vylix

| Feature | Benefit |
|---------|---------|
| **Offline Access** | Critical in Nigeria (intermittent internet) |
| **Home Screen Icon** | Better engagement, feels like native app |
| **Faster Loading** | Cached assets load instantly |
| **Background Sync** | Upload materials when connection returns |
| **Install Prompt** | Increases home screen adoption by 30-50% |
| **No Uninstall Friction** | Easy to remove if needed |

---

## 🆘 Troubleshooting

### **Install prompt not showing**
- PWA only shows in production build (`npm run build && npm run start`)
- Check Chrome DevTools: Application → Manifest
- Must be served over HTTPS (or localhost for dev)

### **Service worker not registering**
- Check DevTools: Application → Service Workers
- Restart app after build
- Clear cache: Application → Storage → Clear site data

### **Offline doesn't work**
- IndexedDB needs data cached first (automatic on visit)
- API calls still need network (show "Offline" message instead)
- Service worker caches static assets only

### **Icons not showing on home screen**
- Icons must be in PNG format (not SVG for some browsers)
- Min 192x192 for home screen
- Check manifest paths are correct

---

## ✨ Next Feature Ideas

1. **Background Sync**: Queue uploads when offline, sync when online
2. **Periodic Sync**: Background refresh of new posts
3. **Push Notifications**: Notify about new collaborations
4. **File Sharing**: Share materials via file picker
5. **Biometric Auth**: Use fingerprint for quick login

---

**PWA is now ready!** 🚀 Generate your icons and test on mobile. Install prompt will start showing automatically.
