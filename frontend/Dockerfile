FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# Dev server with the /api proxy (VITE_API_TARGET points at the backend service).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
