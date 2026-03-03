FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

# Change ownership and switch to non-root 'node' user
RUN chown -R node:node /app
USER node

CMD ["npm", "start"]
