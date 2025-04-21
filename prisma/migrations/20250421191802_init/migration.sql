/*
  Warnings:

  - You are about to drop the `User` table. If the table is not empty, all the data it contains will be lost.

*/
-- CreateEnum
CREATE TYPE "AccountStatus" AS ENUM ('NotLogged', 'Logged', 'NotExist', 'WrongPassword', 'TwoFactorAuthFailed', 'Blocked', 'VerificationRequired');

-- CreateEnum
CREATE TYPE "ProxyStatus" AS ENUM ('NotUsed', 'Used', 'Invalid');

-- DropTable
DROP TABLE "User";

-- CreateTable
CREATE TABLE "Account" (
    "id" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "twoFactorAuthSecret" TEXT NOT NULL,
    "status" "AccountStatus" NOT NULL DEFAULT 'NotLogged',
    "proxyId" TEXT,

    CONSTRAINT "Account_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Proxy" (
    "id" TEXT NOT NULL,
    "proxyUrl" TEXT NOT NULL,
    "status" "ProxyStatus" NOT NULL DEFAULT 'NotUsed',

    CONSTRAINT "Proxy_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Campaign" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "data" JSONB NOT NULL,

    CONSTRAINT "Campaign_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Account_username_key" ON "Account"("username");

-- CreateIndex
CREATE UNIQUE INDEX "Account_proxyId_key" ON "Account"("proxyId");

-- CreateIndex
CREATE UNIQUE INDEX "Proxy_proxyUrl_key" ON "Proxy"("proxyUrl");

-- CreateIndex
CREATE UNIQUE INDEX "Campaign_name_key" ON "Campaign"("name");

-- AddForeignKey
ALTER TABLE "Account" ADD CONSTRAINT "Account_proxyId_fkey" FOREIGN KEY ("proxyId") REFERENCES "Proxy"("id") ON DELETE CASCADE ON UPDATE CASCADE;
