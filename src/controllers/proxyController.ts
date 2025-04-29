import { Prisma, PrismaClient, ProxyStatus } from "@prisma/client";
import { getProxyBaseUrlAndProxyPort } from "../utils/utils";

const prisma = new PrismaClient();

const DATAIMPULSE_API_URL = process.env.DATAIMPULSE_API_URL ?? "";
const DATAIMPULSE_USERNAME = process.env.DATAIMPULSE_USERNAME ?? "";
const DATAIMPULSE_PASSWORD = process.env.DATAIMPULSE_PASSWORD ?? "";

async function fetchDataImpulseProxy(): Promise<{
  proxyBaseUrl: string;
  proxyPort: number;
} | null> {
  console.log(
    "Attempting to fetch a new proxy from DataImpulse using Fetch API...",
  );

  // Construct URL with query string
  const url = new URL(DATAIMPULSE_API_URL);
  url.searchParams.append("countries", "de");
  url.searchParams.append("type", "sticky");
  url.searchParams.append("protocol", "socks5");
  url.searchParams.append("format", "socks5://login:password@hostname:port");
  url.searchParams.append("quantity", "1");

  // Prepare Basic Authentication header
  const basicAuth = Buffer.from(
    `${DATAIMPULSE_USERNAME}:${DATAIMPULSE_PASSWORD}`,
  ).toString("base64");
  const headers = {
    Authorization: `Basic ${basicAuth}`,
  };

  try {
    const res = await fetch(url.toString(), {
      method: "GET",
      headers: headers,
    });

    if (!res.ok) {
      console.error("DataImpulse API Error: Failed to fetch new proxy");
      return null;
    }

    const proxy = (await res.text()).trim();
    if (!proxy) {
      console.error("DataImpulse API Error: Received empty response body.");
      return null;
    }

    console.log(`Successfully fetched and parsed new proxy: PROXY=${proxy}`);
    return getProxyBaseUrlAndProxyPort(proxy);
  } catch (error) {
    console.error(
      "DataImpulse API Error: Failed to fetch new proxy:",
      error instanceof Error ? error.message : error,
    );
    return null;
  }
}

const createProxies = async (
  proxy: { proxyBaseUrl: string; proxyPort: number },
  numberToCreate: number,
) => {
  const { proxyBaseUrl, proxyPort } = proxy;
  const proxiesToCreate: Prisma.ProxyCreateManyInput[] = [];

  for (let i = 0; i < numberToCreate; i++) {
    proxiesToCreate.push({
      proxyUrl: `${proxyBaseUrl}:${(proxyPort + i).toString()}`,
      proxyPort: proxyPort + i,
    });
  }

  const proxyCreateResult = await prisma.proxy.createMany({
    data: proxiesToCreate,
  });

  console.log(
    `Created ${proxyCreateResult.count.toString()} new proxy records.`,
  );
};

const getCreatedProxyIds = async (proxyPort: number, createdNumber: number) => {
  const createdProxies = await prisma.proxy.findMany({
    where: {
      proxyPort: {
        gte: proxyPort,
        lt: proxyPort + createdNumber,
      },
    },
    orderBy: { proxyPort: "asc" },
    select: { id: true },
  });

  return createdProxies.map((p) => p.id);
};

export const createProxiesAndGetTheirIds = async (numberToCreate: number) => {
  const notUsedProxyCount = await prisma.proxy.count({
    where: {
      status: ProxyStatus.NotUsed,
    },
  });

  // check if there is enough unused proxies in DB
  if (notUsedProxyCount >= numberToCreate) {
    const neededProxies = await prisma.proxy.findMany({
      where: {
        status: ProxyStatus.NotUsed,
      },
      take: numberToCreate, // Limit the result to the number of accounts
      select: { id: true },
    });
    console.log(
      `Found and reserved ${neededProxies.length.toString()} available 'NotUsed' proxies.`,
    );
    return neededProxies.map((p) => p.id);
  } else {
    // Check total number of proxies in DB
    const totalProxyCount = await prisma.proxy.count();

    if (totalProxyCount === 0) {
      // fetch from DataImpulse
      console.log(
        "No existing proxies found. Fetching initial proxy from DataImpulse...",
      );

      const proxy = await fetchDataImpulseProxy();

      if (!proxy) {
        console.error("Failed to fetch initial proxy from DataImpulse");
        throw new Error("Failed to fetch initial proxy from DataImpulse");
      }

      await createProxies(proxy, numberToCreate);
      return await getCreatedProxyIds(proxy.proxyPort, numberToCreate);
    } else {
      // If proxies exist, but they're not enough, always create new ones based on the max port.
      console.log("Existing proxies found. Determining next available port...");
      const latestProxy = await prisma.proxy.findFirst({
        orderBy: { proxyPort: "desc" },
      });

      // Should always find one if totalProxyCount > 0, but check just in case
      if (!latestProxy) {
        console.error(
          "Error: Could not find the latest proxy despite totalProxyCount > 0. This indicates a potential data inconsistency.",
        );
        throw new Error("Failed to find latest proxy for port calculation.");
      }

      const proxy = getProxyBaseUrlAndProxyPort(latestProxy.proxyUrl);
      proxy.proxyPort++;

      // Prepare and create proxies for all accounts
      await createProxies(proxy, numberToCreate);
      return await getCreatedProxyIds(proxy.proxyPort, numberToCreate);
    }
  }
};
