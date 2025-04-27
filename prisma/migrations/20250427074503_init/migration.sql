/*
  Warnings:

  - Added the required column `status` to the `Proxy` table without a default value. This is not possible if the table is not empty.

*/
-- CreateEnum
CREATE TYPE "ProxyStatus" AS ENUM ('Used', 'NotUsed');

-- AlterTable
ALTER TABLE "Proxy" ADD COLUMN     "status" "ProxyStatus" NOT NULL;
