import express, { Request, Response } from "express";
import { spawn } from "child_process";
import path from "path";

import { PrismaClient, AccountStatus, Prisma } from "@prisma/client";

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

interface CreateProxyBody {
  proxyUrl: string;
  proxyPort: number;
}

const createProxyHandler = async (
  req: Request<unknown, unknown, CreateProxyBody>,
  res: Response,
) => {
  const { proxyUrl, proxyPort } = req.body;

  if (!proxyUrl || typeof proxyUrl !== "string") {
    res
      .status(400)
      .json({ error: "proxyUrl is required and must be a string" });
    return;
  }

  if (
    !proxyPort ||
    typeof proxyPort !== "number" ||
    !Number.isInteger(proxyPort)
  ) {
    res
      .status(400)
      .json({ error: "proxyPort is required and must be a number" });
    return;
  }

  try {
    const newProxy = await prisma.proxy.create({
      data: {
        proxyUrl,
        proxyPort,
      },
    });
    res.status(201).json(newProxy);
  } catch (error) {
    // Handle potential unique constraint violation (Prisma error code P2002)
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      // Check which field caused the violation
      res.status(409).json({
        error: `Proxy already exists`,
      });
      return;
    }
    // Handle other errors
    console.error("Error creating proxy:", error);
    res
      .status(500)
      .json({ error: "An error occurred while creating the proxy" });
  }
};

interface CreateAccountsBody {
  accounts: string[]; // an array of strings like "email|password|secret|username"
}

const createAccountsHandler = async (
  req: Request<unknown, unknown, CreateAccountsBody>,
  res: Response,
) => {
  const { accounts } = req.body;

  if (
    !Array.isArray(accounts) ||
    accounts.some((item) => typeof item !== "string")
  ) {
    res.status(400).json({
      error: "Request body must contain an 'accounts' array of strings",
    });
    return;
  }

  const accountsToCreate: Prisma.AccountCreateManyInput[] = [];
  const errors: string[] = [];

  accounts.forEach((accountString, index) => {
    const parts = accountString.split("|");
    if (parts.length !== 4) {
      errors.push(
        `Invalid format for account at index ${index.toString()}: Expected 4 parts separated by '|', got ${parts.length.toString()}. String: "${accountString}"`,
      );
      return;
    }
    const [email, password, twoFactorAuthSecret, username] = parts;

    if (!email || !password || !twoFactorAuthSecret || !username) {
      errors.push(
        `Missing data for account at index ${index.toString()}. All parts (email, password, secret, username) are required. String: "${accountString}"`,
      );
      return;
    }

    accountsToCreate.push({
      email,
      password,
      twoFactorAuthSecret,
      username,
    });
  });

  // If there were parsing/validation errors
  if (errors.length > 0) {
    res.status(400).json({
      message: "Some accounts had invalid format or missing data",
      errors: errors,
      createdCount: 0,
    });
    return;
  }

  // If no accounts were valid after parsing
  if (accountsToCreate.length === 0 && accounts.length > 0) {
    res.status(400).json({
      message: "No valid accounts found in the provided list after parsing",
      createdCount: 0,
    });
    return;
  } else if (accountsToCreate.length === 0) {
    res.status(400).json({
      message: "The 'accounts' array was empty.",
      createdCount: 0,
    });
    return;
  }

  try {
    const result = await prisma.account.createMany({
      data: accountsToCreate,
      skipDuplicates: true,
    });

    res.status(201).json({
      message: `Successfully processed batch. Attempted to create ${accountsToCreate.length.toString()} accounts`,
      createdCount: result.count,
    });
    // --- Spawn the login script AFTER sending the response ---
    // This runs as a background task and doesn't block the API response.
    // Only run if accounts were potentially added or intended to be added.
    const loginScriptPath = path.resolve(
      path.dirname(new URL(import.meta.url).pathname),
      "../instagram-login-and-scraper/login/main.py",
    );

    console.log(`Spawning login script: ${loginScriptPath}`);
    const loginProcess = spawn("python3", [loginScriptPath]);

    loginProcess.stdout.on("data", (data: Buffer) => {
      console.log(`[LOGIN SCRIPT STDOUT]: ${data.toString()}`);
    });

    loginProcess.stderr.on("data", (data: Buffer) => {
      console.error(`[LOGIN SCRIPT STDERR]: ${data.toString()}`);
    });

    loginProcess.on("close", (code: number) => {
      console.log(`Login script exited with code ${code.toString()}`);
    });

    loginProcess.on("error", (err) => {
      console.error("Failed to start login script:", err);
    });
  } catch (error) {
    console.error("Error creating accounts in batch:", error);
    res.status(500).json({
      error: "An error occurred during the batch account creation process.",
      createdCount: 0,
    });
  }
};

const getNotLoggedAccountsHandler = async (req: Request, res: Response) => {
  try {
    const notLoggedAccounts = await prisma.account.findMany({
      where: {
        status: AccountStatus.NotLogged, // Filter by status
      },
      include: {
        proxy: true,
      },
    });
    res.json(notLoggedAccounts);
  } catch (error) {
    console.error("Error fetching not logged accounts:", error);
    res.status(500).json({
      error: "An error occurred while fetching not logged accounts",
    });
  }
};

const getMaxProxyPortHandler = async (req: Request, res: Response) => {
  try {
    // Find the proxy with the highest port number
    const proxyWithMaxPort = await prisma.proxy.findFirst({
      orderBy: {
        proxyPort: "desc",
      },
    });

    if (proxyWithMaxPort) {
      res.json({
        maxProxyPort: proxyWithMaxPort.proxyPort as number,
        proxyUrl: proxyWithMaxPort.proxyUrl,
      });
    } else {
      res.json({
        maxProxyPort: null,
        proxyUrl: null,
      });
    }
  } catch (error) {
    console.error("Error fetching max proxy port and URL:", error);
    res.status(500).json({
      error: "An error occurred while fetching the maximum proxy details",
    });
  }
};

// Campaign
app.post("/campaigns", createCampaign);
// Account
app.post("/accounts", createAccountsHandler);
app.get("/accounts/not-logged", getNotLoggedAccountsHandler);
app.patch("/accounts/:id", updateAccountHandler);
// Proxy
app.post("/proxy", createProxyHandler);
app.get("/proxies/max-port", getMaxProxyPortHandler);

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
