import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
} from "amazon-cognito-identity-js";
import config from "../config";

const userPool = new CognitoUserPool({
  UserPoolId: config.cognito.userPoolId,
  ClientId: config.cognito.clientId,
});

export function signUp(email, password) {
  return new Promise((resolve, reject) => {
    const attributes = [
      new CognitoUserAttribute({ Name: "email", Value: email }),
    ];
    userPool.signUp(email, password, attributes, null, (err, result) => {
      if (err) return reject(err);
      resolve(result.user);
    });
  });
}

export function confirmSignUp(email, code) {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool });
    user.confirmRegistration(code, true, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

export function signIn(email, password) {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: userPool });
    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    });
    user.authenticateUser(authDetails, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(err),
    });
  });
}

export function signOut() {
  const user = userPool.getCurrentUser();
  if (user) user.signOut();
}

export function getCurrentUser() {
  return new Promise((resolve, reject) => {
    const user = userPool.getCurrentUser();
    if (!user) return resolve(null);
    user.getSession((err, session) => {
      if (err || !session.isValid()) return resolve(null);
      resolve({ user, session });
    });
  });
}

export function getIdToken() {
  return new Promise((resolve, reject) => {
    const user = userPool.getCurrentUser();
    if (!user) return reject(new Error("Not authenticated"));
    user.getSession((err, session) => {
      if (err) return reject(err);
      resolve(session.getIdToken().getJwtToken());
    });
  });
}

export function getUserId() {
  return new Promise((resolve, reject) => {
    const user = userPool.getCurrentUser();
    if (!user) return reject(new Error("Not authenticated"));
    user.getSession((err, session) => {
      if (err) return reject(err);
      resolve(session.getIdToken().payload.sub);
    });
  });
}
