// Firebase for the deployed dashboard (VITE_FIREBASE=1): the activity calendar listens to Firestore directly,
// everything else goes through the API Cloud Function. The web config is public by design; access is
// limited by firestore.rules (read-only, three collections).
const CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const FIREBASE = import.meta.env.VITE_FIREBASE === '1' && Boolean(CONFIG.projectId);

let db = null;

// Loaded on demand so the local build never pulls the SDK in.
export const firestore = async () => {
  if (db) return db;
  const [{ initializeApp }, fs] = await Promise.all([import('firebase/app'), import('firebase/firestore')]);
  db = { db: fs.getFirestore(initializeApp(CONFIG)), fs };
  return db;
};
