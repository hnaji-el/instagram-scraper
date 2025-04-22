import fs from "fs/promises";
import path from "path";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();
const __dirname = path.dirname(new URL(import.meta.url).pathname);

export async function loadProxiesFromFile() {
  const filePath = path.join(__dirname, "..", "proxies.txt");

  try {
    const content = await fs.readFile(filePath, "utf-8");

    const proxyUrls = content
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"));

    const existingProxies = await prisma.proxy.findMany({
      where: {
        proxyUrl: { in: proxyUrls },
      },
      select: {
        proxyUrl: true,
      },
    });

    const existingProxyUrls = new Set(
      existingProxies.map((proxy) => proxy.proxyUrl),
    );

    const newProxies = proxyUrls
      .filter((url) => !existingProxyUrls.has(url))
      .map((url) => ({ proxyUrl: url }));

    if (newProxies.length > 0) {
      await prisma.proxy.createMany({
        data: newProxies,
      });

      console.log(`Created ${newProxies.length.toString()} new proxy(ies).`);
    } else {
      console.log("No new proxies to create.");
    }
  } catch (error) {
    console.error("Failed to load proxies:", error);
  }
}
