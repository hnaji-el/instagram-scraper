import { Request, Response } from "express";
import { Prisma, PrismaClient } from "@prisma/client";
import { spawn } from "child_process";
import path from "path";

const prisma = new PrismaClient();

interface CreateCampaignBody {
  campaignName: string;
  targets: string[]; // List of usernames or hashtags
  type: "Hashtags" | "Followers"; // What kind of scraping to do
}

export const launchScraper = (
  req: Request<unknown, unknown, CreateCampaignBody>,
  res: Response,
) => {
  const { campaignName, targets, type } = req.body;

  // data validation
  if (
    !campaignName ||
    typeof campaignName !== "string" ||
    campaignName.trim() === ""
  ) {
    res.status(400).json({ error: "campaignName must be a non-empty string." });
    return;
  }

  if (
    !Array.isArray(targets) ||
    targets.length === 0 ||
    !targets.every(
      (target) => typeof target === "string" && target.trim() !== "",
    )
  ) {
    res.status(400).json({
      error: "targets must be a non-empty array of non-empty strings.",
    });
    return;
  }

  if (!(["Hashtags", "Followers"] as const).includes(type)) {
    res
      .status(400)
      .json({ error: 'type must be either "Hashtags" or "Followers".' });
    return;
  }

  try {
    const scriptPath = path.resolve(
      path.dirname(new URL(import.meta.url).pathname),
      "../../instagram-login-and-scraper/scraper/main.py",
    );

    console.log(
      `Attempting to initiate scraper script: ${scriptPath} with args: ${campaignName}, ${JSON.stringify(targets)}, ${type}`,
    );

    const scraper = spawn("python3", [
      "-u", // Unbuffered output
      scriptPath,
      campaignName,
      JSON.stringify(targets),
      type,
    ]);

    scraper.stdout.on("data", (data: Buffer) => {
      console.log(
        `[SCRAPER STDOUT]: ${data.toString().trim()}`,
      );
    });

    scraper.stderr.on("data", (data: Buffer) => {
      console.error(
        `[SCRAPER STDERR]: ${data.toString().trim()}`,
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

    res.status(202).json({
      message: `Scraping campaign '${campaignName}' initiated successfully in the background.`,
      campaign: campaignName,
      type: type,
      targetCount: targets.length,
    });
  } catch (error) {
    console.error(
      `Failed to initiate the scraper script for campaign '${campaignName}':`,
      error,
    );
    res.status(500).json({
      error: `Failed to initiate the scraper script for campaign '${campaignName}'.`,
      details: error instanceof Error ? error.message : String(error),
    });
  }
};

interface CampaignDataItem {
  username: string;
  id: string;
}

export const createCampaign = async (
  req: Request<{ name: string }, unknown, CampaignDataItem[]>,
  res: Response,
) => {
  const { name } = req.params;
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
      where: { name: name },
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
          `Campaign '${name}' data field was not an array. Overwriting with new data. Existing data:`,
          existingCampaign.data,
        );
      }

      // Merge the existing data with the new data
      const updatedData = [...currentData, ...newDataArray];

      // Update the campaign with the complete merged array
      await prisma.campaign.update({
        where: { name: name },
        data: {
          data: updatedData as unknown as Prisma.JsonArray,
        },
      });

      console.log(
        `Successfully updated campaign '${name}' by adding ${newDataArray.length.toString()} items. New total: ${updatedData.length.toString()}.`,
      );
    } else {
      await prisma.campaign.create({
        data: {
          name: name,
          data: newDataArray as unknown as Prisma.JsonArray,
        },
      });
      console.log(
        `Successfully created campaign '${name}' with ${newDataArray.length.toString()} data items.`,
      );
    }

    res.status(200).json({
      message: `Successfully processed ${newDataArray.length.toString()} data items for campaign '${name}'.`,
    });
  } catch (error) {
    console.error(`Error processing data for campaign '${name}':`, error);
    // Handle potential race condition on create (if two requests try to create simultaneously)
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002" // Unique constraint violation
    ) {
      console.warn(
        `Race condition likely occurred for creating campaign '${name}'. Another request might have created it. Retrying might be needed or adjust logic.`,
      );
      // Optionally, you could retry the operation or inform the client differently
      res.status(409).json({
        error: `Conflict: Campaign '${name}' might have been created by a concurrent request.`,
      });
    } else {
      res.status(500).json({
        error: "An error occurred while adding/updating campaign data.",
      });
    }
  }
};

export const getCampaign = async (
  req: Request<{ name: string }>,
  res: Response,
) => {
  const { name } = req.params;

  try {
    const campaign = await prisma.campaign.findUnique({
      where: {
        name: name,
      },
    });

    if (!campaign) {
      res
        .status(404)
        .json({ error: `Campaign with name '${name}' not found.` });
      return;
    }

    res.json(campaign);
  } catch (error) {
    console.error(`Error fetching campaign '${name}':`, error);
    res.status(500).json({
      error: "An error occurred while fetching the campaign.",
    });
  }
};
