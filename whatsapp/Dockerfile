FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund
COPY src/ src/
COPY test/ test/

RUN mkdir -p /app/data && chown -R node:node /app
USER node

VOLUME ["/app/data"]
CMD ["node", "src/index.js"]
