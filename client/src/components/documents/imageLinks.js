import hostData from './imageHosts.json';

const DEAD = new Set(hostData.deadHosts);

export function hostOf(url) {
  if (!/^https?:\/\//i.test(url || '')) return '';
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return '';
  }
}

// A link is hidden when its host is on the audited dead list. A bare file
// name (no host) cannot be followed, so it is hidden too.
export function isHiddenImageLink(url) {
  const h = hostOf(url);
  return h === '' || DEAD.has(h);
}

export function imageLinkLabel(url) {
  const h = hostOf(url);
  const info = hostData.hosts[h];
  if (!info) return `Link at ${h}`;
  const photo = url.match(/edh\.ub\.uni-heidelberg\.de\/edh\/foto\/(F\d+)/i);
  if (photo) return `Photo ${photo[1]} at ${info.name}`;
  return `${info.kind} at ${info.name}`;
}

// downHosts: the detail response's image_hosts_down, [{host, down_since}].
// A down host is hidden like a dead one, but reported separately so the page
// can say which host is unavailable.
export function splitImageLinks(urls, downHosts = []) {
  const down = new Map((downHosts || []).map((d) => [d.host, d]));
  const shown = [];
  const unavailable = [];
  const seen = new Set();
  let omitted = 0;
  for (const u of urls) {
    const h = hostOf(u);
    if (h && down.has(h)) {
      if (!seen.has(h)) {
        seen.add(h);
        unavailable.push({
          host: h,
          name: hostData.hosts[h]?.name || h,
          down_since: down.get(h).down_since || null,
        });
      }
    } else if (isHiddenImageLink(u)) omitted += 1;
    else shown.push({ url: u, label: imageLinkLabel(u) });
  }
  return { shown, omitted, unavailable };
}
