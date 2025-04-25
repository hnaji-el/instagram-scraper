import express, { Request, Response } from "express";
import { spawn } from "child_process";
import path from "path";

import { PrismaClient, AccountStatus, Prisma } from "@prisma/client";

import { loadAccountsFromFile } from "./loadAccountsFromFile";

const app = express();
app.use(express.json());

const prisma = new PrismaClient();

const port = process.env.PORT ?? "3000";
const domain = process.env.DOMAIN ?? "";

interface UpdateAccountBody {
  status?: AccountStatus;
  sessionData?: Prisma.JsonValue;
  proxyId?: string;
}

const updateAccountHandler = async (
  req: Request<{ id: string }, unknown, UpdateAccountBody>,
  res: Response,
) => {
  const { id } = req.params;
  const { status, sessionData, proxyId } = req.body;

  if (!status && !sessionData && !proxyId) {
    res.status(400).json({
      error: "Provide at least one of 'status' or 'proxyId' to update",
    });
    return;
  }

  if (status && !Object.values(AccountStatus).includes(status)) {
    res.status(400).json({ error: "status is not valid" });
    return;
  }

  try {
    const account = await prisma.account.update({
      where: { id },
      data: {
        ...(status && { status }),
        ...(sessionData && { sessionData }),
        ...(proxyId && { proxyId }),
      },
    });

    res.json(account);
  } catch (error) {
    console.error(error);
    res.status(500).json({
      error: "An error occurred while updating the account",
    });
  }
};

interface CreateCampaignBody {
  campaignName: string;
  targets: string[]; // List of usernames or hashtags
  type: "Hashtags" | "Followers"; // What kind of scraping to do
}

const createCampaign = (
  req: Request<unknown, unknown, CreateCampaignBody>,
  res: Response,
) => {
  const { campaignName, targets, type } = req.body;
  const scriptPath = path.resolve(
    path.dirname(new URL(import.meta.url).pathname),
    "../instagram-login-and-scraper/scraper/main.py",
  );

  const scraper = spawn("python3", [
    scriptPath,
    campaignName,
    JSON.stringify(targets),
    type,
  ]);

  scraper.stdout.on("data", (data: Buffer) => {
    console.log(`[SCRAPER STDOUT]: ${data.toString()}`);
  });

  scraper.stderr.on("data", (data: Buffer) => {
    console.error(`[SCRAPER STDERR]: ${data.toString()}`);
  });

  scraper.on("close", (code: number) => {
    console.log(`Scraper script exited with code ${code.toString()}`);
    if (code === 0) {
      res.status(200).json({ message: "Scraper script ran successfully." });
    } else {
      res
        .status(500)
        .json({ error: `Scraper Script exited with code ${code.toString()}` });
    }
  });

  scraper.on("error", (err) => {
    console.error("Failed to start scraper script", err);
    res.status(500).json({ error: "Failed to start scraper script" });
  });
};

const getActiveAccountsHandler = async (req: Request, res: Response) => {
  try {
    const accounts = await prisma.account.findMany({
      where: {
        status: {
          notIn: [
            AccountStatus.NotExist,
            AccountStatus.WrongPassword,
            AccountStatus.TwoFactorAuthFailed,
          ],
        },
      },
    });
    res.json(accounts);
  } catch (error) {
    console.error(error);
    res.status(500).json({
      error: "An error occurred while fetching active accounts",
    });
  }
};

// Campaign
app.post("/campaigns", createCampaign);
// Account
// app.get("/accounts", createAccounts); // TODO:
app.patch("/accounts/:id", updateAccountHandler);
app.get("/accounts/active", getActiveAccountsHandler);
// Proxy
// app.get("/proxy", createProxy); // TODO:

await loadAccountsFromFile();

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
