# Daily Check

This is the original Firebase-backed attendance app. It is separate from the portfolio's safe, local-only preview in `demos/daily-check/`.

## Configure Firebase

1. Copy `firebase-config.example.js` to `firebase-config.js`.
2. Fill in the configuration for your own Firebase project.
3. Configure and test Firestore Security Rules before enabling writes.
4. Keep `firebase-config.js` out of Git; it is ignored by `.gitignore`.

Serve this folder over HTTP(S) to run the app. It imports the Firebase Web SDK from Google's CDN.

