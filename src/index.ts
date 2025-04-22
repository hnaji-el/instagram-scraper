import express from "express";
import { PrismaClient } from "@prisma/client";

const app = express();
app.use(express.json());

const prisma = new PrismaClient();

const port = process.env.PORT ?? "3000";
const domain = process.env.DOMAIN ?? "";

app.patch("/accounts/:id", async (req, res) => {
  const { id } = req.params;
  const { status, proxyId } = req.body;

  if (!status && !proxyId) {
    res.status(400).json({
      error: "Provide at least one of 'status' or 'proxyId' to update",
    });
    return;
  }

  try {
    const account = await prisma.account.update({
      where: { id },
      data: {
        ...(status && { status }),
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
});

app.patch("/proxies/:id", async (req, res) => {
  const { id } = req.params;
  const { status } = req.body;

  if (!status) {
    res.status(400).json({ error: "Status is required" });
    return;
  }

  try {
    const updatedProxy = await prisma.proxy.update({
      where: { id },
      data: { status },
    });

    res.json(updatedProxy);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Failed to update proxy" });
  }
});

app.get("/", (req, res) => {
  res.send("Hello World!");
  console.log("Response sent");
});

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
