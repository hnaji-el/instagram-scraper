import express from "express";

import {
  createAccounts,
  getLoggedAccounts,
  getNotLoggedAccounts,
  launchLogin,
  updateAccount,
  updateAccountsActivity,
} from "./controllers/accountControllers.js";
import {
  createCampaign,
  getCampaign,
  launchScraper,
} from "./controllers/campaignController.js";

const port = process.env.PORT ?? "3000";
const domain = process.env.DOMAIN ?? "";

const app = express();
app.use(express.json());

// Campaign
app.post("/launch-scraper", launchScraper);
app.post("/campaigns/:name", createCampaign);
app.get("/campaigns/:name", getCampaign);
// Account
app.post("/launch-login", launchLogin);
app.post("/accounts", createAccounts);
app.get("/accounts/not-logged", getNotLoggedAccounts);
app.get("/accounts/logged", getLoggedAccounts);
app.patch("/accounts/activity", updateAccountsActivity);
app.patch("/accounts/:id", updateAccount);

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
