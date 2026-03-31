FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
RUN npm install --omit=dev --ignore-scripts
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm", "run", "start"]
