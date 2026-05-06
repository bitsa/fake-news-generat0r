FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install && chown -R node:node /app
COPY --chown=node:node . .
USER node
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
