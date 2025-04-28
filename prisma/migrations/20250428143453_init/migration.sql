/*
  Warnings:

  - You are about to drop the column `isNotActive` on the `Account` table. All the data in the column will be lost.
  - You are about to drop the column `isNotActiveStartTime` on the `Account` table. All the data in the column will be lost.

*/
-- AlterTable
ALTER TABLE "Account" DROP COLUMN "isNotActive",
DROP COLUMN "isNotActiveStartTime",
ADD COLUMN     "isActive" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "isActiveUpdatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
