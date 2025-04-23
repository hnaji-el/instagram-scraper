FROM node:22-alpine3.20

WORKDIR /app

RUN apk add --no-cache python3 py3-pip

EXPOSE 3000
EXPOSE 5555

CMD ["sh", "-c", "npm install ; npx prisma migrate dev --name init ; npm run dev"]