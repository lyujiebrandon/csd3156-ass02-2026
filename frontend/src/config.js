// Values are injected at build time from environment variables.
// Create a .env.local file locally, or set them in GitHub Actions secrets.
const config = {
  cognito: {
    region: process.env.REACT_APP_AWS_REGION || "ap-southeast-1",
    userPoolId: process.env.REACT_APP_COGNITO_USER_POOL_ID || "",
    clientId: process.env.REACT_APP_COGNITO_CLIENT_ID || "",
  },
  api: {
    baseUrl: process.env.REACT_APP_API_URL || "",
  },
  websocket: {
    url: process.env.REACT_APP_WEBSOCKET_URL || "",
  },
};

export default config;
