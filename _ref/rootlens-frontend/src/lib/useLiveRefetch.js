import { useEffect, useRef } from 'react';
import { FIREBASE, firestore } from './firebase';

// Keeps an API-backed list in step with the other client (the Android app or another browser): when a row
// is added or changed in the Firestore collection, refetch. Deployed builds only; local dev has no Firestore.
export const useLiveRefetch = (collection, refetch) => {
  const latest = useRef(refetch);
  latest.current = refetch;
  useEffect(() => {
    if (!FIREBASE) return undefined;
    let unsub = () => {};
    let first = true;
    let closed = false;
    firestore().then(({ db, fs }) => {
      if (closed) return;
      const q = fs.query(fs.collection(db, collection), fs.orderBy('created', 'desc'), fs.limit(50));
      unsub = fs.onSnapshot(q, () => {
        if (first) {
          first = false; // the initial snapshot is what the list already shows
          return;
        }
        latest.current?.();
      });
    });
    return () => {
      closed = true;
      unsub();
    };
  }, [collection]);
};
