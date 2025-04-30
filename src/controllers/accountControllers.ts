import { Request, Response } from "express";
import {
  PrismaClient,
  Prisma,
  ProxyStatus,
  AccountStatus,
} from "@prisma/client";
import { spawn } from "child_process";
import path from "path";
import { createProxiesAndGetTheirIds } from "./proxyController";

const prisma = new PrismaClient();

export const spawnLoginProcess = () => {
  const scriptPath = path.resolve(
    path.dirname(new URL(import.meta.url).pathname),
    "../../instagram-login-and-scraper/login/main.py",
  );

  console.log(`Attempting to initiate login script: ${scriptPath}`);

  const loginProcess = spawn("python3", ["-u", scriptPath]);

  loginProcess.stdout.on("data", (data: Buffer) => {
    console.log(`[LOGIN STDOUT]: ${data.toString()}`);
  });

  loginProcess.stderr.on("data", (data: Buffer) => {
    console.error(`[LOGIN STDERR]: ${data.toString()}`);
  });

  loginProcess.on("close", (code: number) => {
    console.log(`Login script exited with code ${code.toString()}`);
  });

  loginProcess.on("error", (err) => {
    console.error("Failed to run login script:", err);
  });
};

export const launchLogin = (req: Request, res: Response) => {
  try {
    spawnLoginProcess();

    res.status(202).json({
      message: "Logging process initiated successfully in the background.",
    });
  } catch (error) {
    console.error("Failed to initiate the login script:", error);
    res.status(500).json({
      error: "Failed to initiate the login script.",
      details: error instanceof Error ? error.message : String(error),
    });
  }
};

const filterAccounts = async (accounts: Prisma.AccountCreateManyInput[]) => {
  const usernamesToCheck = accounts.map((account) => account.username);

  // Find existing accounts with these usernames
  const existingAccounts = await prisma.account.findMany({
    where: {
      username: {
        in: usernamesToCheck,
      },
    },
    select: {
      username: true,
    },
  });

  const existingUsernames = new Set(
    existingAccounts.map((acc) => acc.username),
  );

  // Filter the original array
  const filteredAccounts = accounts.filter(
    (account) => !existingUsernames.has(account.username),
  );

  return {
    filteredAccounts,
    skippedAccountsCount: accounts.length - filteredAccounts.length,
  };
};

const parseAccounts = (accounts: string[]) => {
  const parsedAccounts: Prisma.AccountCreateManyInput[] = [];
  const errors: string[] = [];

  accounts.forEach((account, index) => {
    const parts = account.split("|");

    if (parts.length !== 4) {
      errors.push(
        `Invalid format for account at index ${index.toString()}: Expected 4 parts separated by '|', got ${parts.length.toString()}. String: "${account}"`,
      );
      return;
    }
    const [email, password, twoFactorAuthSecret, username] = parts;

    if (!email || !password || !twoFactorAuthSecret || !username) {
      errors.push(
        `Missing data for account at index ${index.toString()}. All parts (email, password, secret, username) are required. String: "${account}"`,
      );
      return;
    }

    parsedAccounts.push({
      email,
      password,
      twoFactorAuthSecret,
      username,
    });
  });

  return { parsedAccounts, errors };
};

interface CreateAccountsBody {
  accounts: string[]; // an array of strings like "email|password|secret|username"
}

export const createAccounts = async (
  req: Request<unknown, unknown, CreateAccountsBody>,
  res: Response,
) => {
  const { accounts } = req.body;

  if (
    !Array.isArray(accounts) ||
    accounts.length === 0 ||
    accounts.some((item) => typeof item !== "string")
  ) {
    res.status(400).json({
      error: "Request body must contain an 'accounts' array of strings",
    });
    return;
  }

  const { parsedAccounts, errors } = parseAccounts(accounts);

  // If there were parsing errors
  if (errors.length > 0) {
    res.status(400).json({
      message: "Some accounts had invalid format or missing data",
      errors: errors,
    });
    return;
  }

  let filteredAccounts: Prisma.AccountCreateManyInput[] = [];
  let skippedAccountsCount = 0;

  try {
    // Filter out accounts that already exist in the DB
    const result = await filterAccounts(parsedAccounts);
    filteredAccounts = result.filteredAccounts;
    skippedAccountsCount = result.skippedAccountsCount;

    // If all accounts already existed
    if (filteredAccounts.length === 0) {
      console.log(
        "All provided accounts already exist in the database. No new accounts were created.",
      );
      res.status(200).json({
        message:
          "All provided accounts already exist in the database. No new accounts were created.",
        createdCount: 0,
        skippedCount: skippedAccountsCount,
      });
      return;
    }
  } catch (err) {
    console.error("Error checking for existing accounts:", err);
    res.status(500).json({
      error: "An error occurred while checking for existing accounts.",
    });
    return;
  }

  // Proxy Preparation
  let proxyIdsToAssign: string[] = []; // Array to hold the proxy IDs

  try {
    console.log("Starting proxy preparation...");

    proxyIdsToAssign = await createProxiesAndGetTheirIds(
      filteredAccounts.length,
    );

    filteredAccounts.forEach((account, index) => {
      account.proxyId = proxyIdsToAssign[index];
    });
  } catch (err) {
    console.error("Error during proxy preparation:", err);
    res
      .status(500)
      .json({ error: "An error occurred during proxy preparation." });
    return;
  }
  // End Proxy Preparation

  try {
    // Wrap account creation and proxy update in a transaction
    await prisma.$transaction([
      prisma.account.createMany({
        data: filteredAccounts,
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

    // give a message to log it about creating accounts and skipping accounts and updating proxies
    console.log(
      `Created ${filteredAccounts.length.toString()} new accounts (skipped ${skippedAccountsCount.toString()}). Updated ${proxyIdsToAssign.length.toString()} proxies to status 'Used'.`,
    );

    spawnLoginProcess();

    res.status(201).json({
      message: `Successfully created ${filteredAccounts.length.toString()} new accounts (skipped ${skippedAccountsCount.toString()}). Login process initiated.`,
      createdCount: filteredAccounts.length,
      skippedCount: skippedAccountsCount,
    });
  } catch (error) {
    console.error("Error creating accounts in batch:", error);
    res.status(500).json({
      error: "An error occurred during the batch account creation process.",
      createdCount: 0,
    });
  }
};

export const getNotLoggedAccounts = async (req: Request, res: Response) => {
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

export const getLoggedAccounts = async (req: Request, res: Response) => {
  const countParam = req.query.count as string;
  const count = +countParam;

  if (!countParam || isNaN(count) || count <= 0) {
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
      orderBy: {
        isActiveUpdatedAt: "asc", // oldest inactive first to prioritize using them
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

interface UpdateAccountBody {
  status?: AccountStatus;
  sessionData?: Prisma.JsonValue;
  proxyId?: string;
}

export const updateAccount = async (
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
    console.log(
      "#####################################################################",
    );
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

interface UpdateMultipleAccountsActivityBody {
  accountIds: string[];
  isActive: boolean;
}

export const updateAccountsActivity = async (
  req: Request<unknown, unknown, UpdateMultipleAccountsActivityBody>,
  res: Response,
) => {
  const { accountIds, isActive } = req.body;

  if (
    !Array.isArray(accountIds) ||
    accountIds.length === 0 ||
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

    console.log(
      `Successfully attempted to update activity status for ${accountIds.length.toString()} accounts.`,
    );

    res.json({
      message: `Successfully attempted to update activity status for ${accountIds.length.toString()} accounts.`,
      updatedCount: updateResult.count,
      requestedStatus: { isActive },
    });
  } catch (error) {
    console.error(`Error during bulk update of account activity:`, error);
    res.status(500).json({
      error: "An error occurred while updating account activity status.",
    });
  }
};
