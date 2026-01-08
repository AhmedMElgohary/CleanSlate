FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

# We use "--host" to expose it to the network
CMD ["npm", "run", "dev", "--", "--host"]