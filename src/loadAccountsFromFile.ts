import fs from "fs/promises";
import path from "path";

import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();
const __dirname = path.dirname(new URL(import.meta.url).pathname);

export async function loadAccountsFromFile() {
  const filePath = path.join(__dirname, "..", "accounts.txt");

  try {
    const content = await fs.readFile(filePath, "utf-8");

    const lines = content
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"));

    const accountsFromFile = lines
      .map((line) => {
        const [email, password, twoFactorAuthSecret, username] =
          line.split("|");
        if (!email || !password || !twoFactorAuthSecret || !username)
          return null;

        return { email, password, twoFactorAuthSecret, username };
      })
      .filter((acc) => acc !== null);

    const usernames = accountsFromFile.map((acc) => acc.username);

    const existingAccounts = await prisma.account.findMany({
      where: {
        username: { in: usernames },
      },
      select: {
        username: true,
      },
    });

    const existingUsernames = new Set(
      existingAccounts.map((acc) => acc.username),
    );

    const newAccounts = accountsFromFile.filter(
      (acc) => !existingUsernames.has(acc.username),
    );

    if (newAccounts.length > 0) {
      await prisma.account.createMany({
        data: newAccounts,
      });

      console.log(`Created ${newAccounts.length.toString()} new account(s)`);
    } else {
      console.log("No new accounts to create");
    }
  } catch (error) {
    console.error("Failed to load accounts:", error);
  }
}
