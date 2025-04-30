-- CreateEnum
CREATE TYPE "AccountStatus" AS ENUM ('Logged', 'NotLogged', 'NotExist', 'WrongPassword', 'TwoFactorAuthFailed', 'Blocked', 'CheckpointRequired', 'ChallengeRequired');

-- CreateEnum
CREATE TYPE "ProxyStatus" AS ENUM ('Used', 'NotUsed');

-- CreateTable
CREATE TABLE "Account" (
    "id" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "twoFactorAuthSecret" TEXT NOT NULL,
    "status" "AccountStatus" NOT NULL DEFAULT 'NotLogged',
    "isActive" BOOLEAN NOT NULL DEFAULT false,
    "isActiveUpdatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "sessionData" JSONB,
    "proxyId" TEXT,

    CONSTRAINT "Account_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Proxy" (
    "id" TEXT NOT NULL,
    "proxyUrl" TEXT NOT NULL,
    "proxyPort" INTEGER NOT NULL,
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
CREATE UNIQUE INDEX "Proxy_proxyPort_key" ON "Proxy"("proxyPort");

-- CreateIndex
CREATE UNIQUE INDEX "Campaign_name_key" ON "Campaign"("name");

-- AddForeignKey
ALTER TABLE "Account" ADD CONSTRAINT "Account_proxyId_fkey" FOREIGN KEY ("proxyId") REFERENCES "Proxy"("id") ON DELETE CASCADE ON UPDATE CASCADE;
