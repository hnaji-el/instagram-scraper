export function getProxyBaseUrlAndProxyPort(proxy: string): {
  proxyBaseUrl: string;
  proxyPort: number;
} {
  const proxyParts = proxy.split(":");
  const proxyPort = parseInt(proxyParts[proxyParts.length - 1], 10);
  const proxyBaseUrl = proxyParts.slice(0, -1).join(":");

  return { proxyBaseUrl, proxyPort };
}
