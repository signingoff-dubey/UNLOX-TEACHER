import { useEffect, useState } from 'react';

// Tiny hash router: #/board, #/asset/locals-kn-whatsapp. Keeps pages linkable without a server.
const parse = () => {
  const [, slug = 'home', param] = window.location.hash.replace(/^#/, '').split('/');
  return { slug: slug || 'home', param: param ? decodeURIComponent(param) : undefined };
};

export const navigate = (slug, param) => {
  window.location.hash = param ? `/${slug}/${encodeURIComponent(param)}` : `/${slug}`;
};

export const useRoute = () => {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const onChange = () => {
      setRoute(parse());
      document.querySelector('main')?.scrollTo({ top: 0 });
    };
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
};
