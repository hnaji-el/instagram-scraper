import express from "express";

const app = express();

const port = process.env.PORT ?? "3000";
const domain = process.env.DOMAIN ?? "";

app.get("/", (req, res) => {
  res.send("Hello World!");
  console.log("Response sent");
});

app.listen(port, () => {
  console.log(`Server is running on ${domain}:${port}`);
});
