import express, { Request, Response } from "express";
import { spawn } from "child_process";
import path from "path";

import {
  PrismaClient,
  AccountStatus,
  Prisma,
  ProxyStatus,
} from "@prisma/client";

const app = express();
app.use(express.json());

const prisma = new PrismaClient();

const port = process.env.PORT ?? "3000";
const domain = process.env.DOMAIN ?? "";

const DATAIMPULSE_API_URL = process.env.DATAIMPULSE_API_URL ?? "";
const DATAIMPULSE_USERNAME = process.env.DATAIMPULSE_USERNAME ?? "";
const DATAIMPULSE_PASSWORD = process.env.DATAIMPULSE_PASSWORD ?? "";

function getProxyBaseUrlAndProxyPort(proxy: string): {
  proxyBaseUrl: string;
  proxyPort: number;
} {
  const proxyParts = proxy.split(":");
  const proxyPort = parseInt(proxyParts[proxyParts.length - 1], 10);
  const proxyBaseUrl = proxyParts.slice(0, -1).join(":");

  return { proxyBaseUrl, proxyPort };
}

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

  try {
    console.log(
      `Attempting to spawn scraper script: ${scriptPath} with args: ${campaignName}, ${JSON.stringify(targets)}, ${type}`,
    );
    const scraper = spawn("python3", [
      "-u", // Unbuffered output
      scriptPath,
      campaignName,
      JSON.stringify(targets), // Pass targets as a JSON string
      type,
    ]);

    // Event listeners for background logging
    scraper.stdout.on("data", (data: Buffer) => {
      console.log(
        `[SCRAPER STDOUT - ${campaignName}]: ${data.toString().trim()}`,
      );
    });

    scraper.stderr.on("data", (data: Buffer) => {
      console.error(
        `[SCRAPER STDERR - ${campaignName}]: ${data.toString().trim()}`,
      );
    });

    scraper.on("close", (code: number) => {
      console.log(
        `Scraper script for campaign '${campaignName}' exited with code ${code.toString()}`,
      );
    });

    scraper.on("error", (err) => {
      console.error(
        `Failed to run scraper script for campaign '${campaignName}':`,
        err,
      );
    });

    // 202 Accepted: The request has been accepted for processing,
    // but the processing has not been completed.
    res.status(202).json({
      message: `Scraping campaign '${campaignName}' started successfully in the background.`,
      campaign: campaignName,
      type: type,
      targetCount: targets.length,
    });
  } catch (error) {
    console.error(
      `Error spawning scraper script for campaign '${campaignName}':`,
      error,
    );
    res.status(500).json({
      error: "Failed to start the scraper script.",
      details: error instanceof Error ? error.message : String(error),
    });
  }
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

const createProxiesAndGetTheirIds = async (numberToCreate: number) => {
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

  // If there is no accounts
  if (accountsToCreate.length === 0) {
    res.status(400).json({
      message: "The 'accounts' array was empty",
      createdCount: 0,
    });
    return;
  }

  // --- Proxy Preparation ---
  let proxyIdsToAssign: string[] = []; // Array to hold the proxy IDs

  try {
    console.log("Starting proxy preparation...");

    proxyIdsToAssign = await createProxiesAndGetTheirIds(
      accountsToCreate.length,
    );

    accountsToCreate.forEach((account, index) => {
      account.proxyId = proxyIdsToAssign[index];
    });
  } catch (proxyError) {
    console.error("Error during proxy preparation:", proxyError);
    res
      .status(500)
      .json({ error: "An error occurred during proxy preparation." });
    return;
  }
  // --- End Proxy Preparation ---

  try {
    // Wrap account creation and proxy update in a transaction
    const [result] = await prisma.$transaction([
      prisma.account.createMany({
        data: accountsToCreate,
      }),
      prisma.proxy.updateMany({
        where: {
          id: {
            in: proxyIdsToAssign, // Target proxies whose IDs were assigned
          },
        },
        data: {
          status: ProxyStatus.Used, // Set their status to Used
        },
      }),
    ]);

    console.log(
      `Updated status for ${proxyIdsToAssign.length.toString()} proxies to 'Used'.`,
    );

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
    const loginProcess = spawn("python3", ["-u", loginScriptPath]);

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
        maxProxyPort: proxyWithMaxPort.proxyPort,
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

const getLoggedAccountsHandler = async (req: Request, res: Response) => {
  const countParam = req.query.count as string;
  const count = +countParam;

  if (
    !countParam ||
    isNaN(parseInt(countParam, 10)) ||
    parseInt(countParam, 10) <= 0
  ) {
    res
      .status(400)
      .json({ error: "Query parameter 'count' must be a positive integer." });
    return;
  }

  try {
    // Calculate the timestamp for 30 seconds ago
    const thirtySecondsAgo = new Date(Date.now() - 30 * 1000);

    const loggedAccounts = await prisma.account.findMany({
      where: {
        status: AccountStatus.Logged,
        isActive: false, // Account must be inactive
        isActiveUpdatedAt: {
          lte: thirtySecondsAgo, // And it must have been inactive since at least 30 seconds ago
        },
      },
      take: count, // Limit the number of results
      include: {
        proxy: true,
      },
      //  oldest inactive first to prioritize using them
      orderBy: {
        isActiveUpdatedAt: "asc",
      },
    });

    if (loggedAccounts.length === 0) {
      console.log(
        "No logged accounts found matching the criteria (Logged, isActive=false for >= 30s).",
      );
    }

    res.json(loggedAccounts);
  } catch (error) {
    console.error("Error fetching logged accounts:", error);
    res.status(500).json({
      error: "An error occurred while fetching logged accounts",
    });
  }
};

interface CampaignDataItem {
  username: string;
  id: string;
}

const addCampaignDataHandler = async (
  req: Request<{ campaignName: string }, unknown, CampaignDataItem[]>,
  res: Response,
) => {
  const { campaignName } = req.params;
  const newDataArray = req.body;

  // Validation for the incoming array
  if (!Array.isArray(newDataArray)) {
    res
      .status(400)
      .json({ error: "Invalid data format. Request body must be an array." });
    return;
  }
  if (newDataArray.length === 0) {
    res
      .status(200)
      .json({ message: "Received empty data array. No changes made." });
    return;
  }

  try {
    const existingCampaign = await prisma.campaign.findUnique({
      where: { name: campaignName },
      select: { data: true },
    });

    if (existingCampaign) {
      // --- Campaign exists: Fetch, Merge, and Update ---
      let currentData: CampaignDataItem[] = [];

      // Safely check if existingCampaign.data is an array
      if (Array.isArray(existingCampaign.data)) {
        currentData = existingCampaign.data as unknown as CampaignDataItem[];
      } else if (existingCampaign.data !== null) {
        // Log a warning if data exists but isn't an array (unexpected state)
        console.warn(
          `Campaign '${campaignName}' data field was not an array. Overwriting with new data. Existing data:`,
          existingCampaign.data,
        );
      }

      // Merge the existing data with the new data
      const updatedData = [...currentData, ...newDataArray];

      // Update the campaign with the complete merged array
      await prisma.campaign.update({
        where: { name: campaignName },
        data: {
          data: updatedData as unknown as Prisma.JsonArray,
        },
      });

      console.log(
        `Successfully updated campaign '${campaignName}' by adding ${newDataArray.length.toString()} items. New total: ${updatedData.length.toString()}.`,
      );
    } else {
      await prisma.campaign.create({
        data: {
          name: campaignName,
          data: newDataArray as unknown as Prisma.JsonArray,
        },
      });
      console.log(
        `Successfully created campaign '${campaignName}' with ${newDataArray.length.toString()} data items.`,
      );
    }

    res.status(200).json({
      message: `Successfully processed ${newDataArray.length.toString()} data items for campaign '${campaignName}'.`,
    });
  } catch (error) {
    console.error(
      `Error processing data for campaign '${campaignName}':`,
      error,
    );
    // Handle potential race condition on create (if two requests try to create simultaneously)
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002" // Unique constraint violation
    ) {
      console.warn(
        `Race condition likely occurred for creating campaign '${campaignName}'. Another request might have created it. Retrying might be needed or adjust logic.`,
      );
      // Optionally, you could retry the operation or inform the client differently
      res.status(409).json({
        error: `Conflict: Campaign '${campaignName}' might have been created by a concurrent request.`,
      });
    } else {
      res.status(500).json({
        error: "An error occurred while adding/updating campaign data.",
      });
    }
  }
};

const getCampaignByNameHandler = async (
  req: Request<{ campaignName: string }>,
  res: Response,
) => {
  const { campaignName } = req.params;

  try {
    const campaign = await prisma.campaign.findUnique({
      where: {
        name: campaignName,
      },
    });

    if (!campaign) {
      res
        .status(404)
        .json({ error: `Campaign with name '${campaignName}' not found.` });
      return;
    }

    res.json(campaign);
  } catch (error) {
    console.error(`Error fetching campaign '${campaignName}':`, error);
    res.status(500).json({
      error: "An error occurred while fetching the campaign.",
    });
  }
};

interface UpdateMultipleAccountsActivityBody {
  accountIds: string[];
  isActive: boolean;
}

const updateAccountsActivityHandler = async (
  req: Request<unknown, unknown, UpdateMultipleAccountsActivityBody>,
  res: Response,
) => {
  const { accountIds, isActive } = req.body;

  if (
    !Array.isArray(accountIds) ||
    accountIds.some((id) => typeof id !== "string")
  ) {
    res
      .status(400)
      .json({ error: "'accountIds' must be an array of strings." });
    return;
  }
  if (typeof isActive !== "boolean") {
    res.status(400).json({
      error: "'isNotActive' must be a boolean value (true or false).",
    });
    return;
  }
  if (accountIds.length === 0) {
    res.status(400).json({ error: "'accountIds' array cannot be empty." });
    return;
  }

  try {
    const updateResult = await prisma.account.updateMany({
      where: {
        id: {
          in: accountIds,
        },
      },
      data: {
        isActive: isActive,
        isActiveUpdatedAt: new Date(),
      },
    });

    res.json({
      message: `Successfully attempted to update activity status for ${accountIds.length.toString()} accounts.`,
      updatedCount: updateResult.count,
      requestedStatus: { isActive },
    });
  } catch (error) {
    console.error(`Error during bulk update of account activity:`, error);
    // Note: updateMany doesn't throw specific "not found" errors like update does.
    // It simply updates 0 records if none match.
    res.status(500).json({
      error: "An error occurred while updating account activity status.",
    });
  }
};

// Campaign
app.post("/campaigns", createCampaign);
app.post("/campaigns/:campaignName/data", addCampaignDataHandler);
app.get("/campaigns/:campaignName", getCampaignByNameHandler);
// Account
app.post("/accounts", createAccountsHandler);
app.get("/accounts/not-logged", getNotLoggedAccountsHandler);
app.get("/accounts/logged", getLoggedAccountsHandler);
app.patch("/accounts/:id", updateAccountHandler);
app.patch("/accounts/activity", updateAccountsActivityHandler);
// Proxy
app.post("/proxy", createProxyHandler);
app.get("/proxies/max-port", getMaxProxyPortHandler);

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
