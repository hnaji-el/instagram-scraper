FROM node:22-alpine3.20

WORKDIR /app

RUN apk add --no-cache python3 py3-pip build-base python3-dev

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY ./instagram-scraper/requirements.txt ./instagram-scraper/

RUN pip install --no-cache-dir -r instagram-scraper/requirements.txt

EXPOSE 3000
EXPOSE 5555

CMD ["sh", "-c", "npm install ; npx prisma migrate dev --name init ; npm run dev"]