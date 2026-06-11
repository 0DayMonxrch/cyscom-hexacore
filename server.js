const express = require('express');
const session = require('express-session');
const http = require('http');
const https = require('https');
const bodyParser = require('body-parser');
const path = require('path');
const url = require('url');

const app = express();

// Parse form and JSON bodies
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());

// Serve static files from /public
app.use(express.static('public'));

// Sessions
app.use(
  session({
    secret: process.env.SESSION_SECRET || 'change-this-secret-in-production',
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: 'strict',
      maxAge: 1000 * 60 * 60 * 24
    }
  })
);

// ---------- Helper to talk to Python ----------
// PYTHON_URL is set as an env var on Render, e.g. https://fastapi-node-auth-api.onrender.com
const PYTHON_BASE_URL = process.env.PYTHON_URL || 'http://127.0.0.1:8080';

function callPython(pathName, payload, callback) {
  const data = JSON.stringify(payload);
  const parsedUrl = url.parse(PYTHON_BASE_URL + pathName);
  const isHttps = parsedUrl.protocol === 'https:';
  const lib = isHttps ? https : http;

  const options = {
    hostname: parsedUrl.hostname,
    port: parsedUrl.port || (isHttps ? 443 : 80),
    path: parsedUrl.path,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(data),
    },
  };

  const req = lib.request(options, (res) => {
    let body = '';
    res.on('data', (chunk) => (body += chunk));
    res.on('end', () => {
      try {
        callback(null, JSON.parse(body));
      } catch (err) {
        callback(err);
      }
    });
  });

  req.on('error', (err) => {
    console.error('Error calling Python:', err);
    callback(err);
  });

  req.write(data);
  req.end();
}

function sendToPythonLogin(userid, password, cb) {
  callPython('/login', { userid, password }, cb);
}

function sendToPythonRegister(userid, password, cb) {
  callPython('/register', { userid, password }, cb);
}

// ---------- Routes ----------

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/session', (req, res) => {
  if (req.session.user) {
    res.json({ loggedIn: true, user: req.session.user });
  } else {
    res.json({ loggedIn: false });
  }
});

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'login.html'));
});

app.post('/login', (req, res) => {
  const { userid, password } = req.body;
  if (!userid || !password) return res.status(400).send('Missing fields');

  sendToPythonLogin(userid, password, (err, response) => {
    if (err || response.status !== 'success') {
      return res.status(401).send('Login failed: Invalid credentials');
    }
    req.session.user = response.user;
    res.redirect('/');
  });
});

app.get('/register', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'register.html'));
});

app.post('/register', (req, res) => {
  const { userid, password } = req.body;
  if (!userid || !password) return res.status(400).send('Missing fields');

  sendToPythonRegister(userid, password, (err, response) => {
    if (err || response.status !== 'success') {
      return res.status(400).send('Registration failed: ' + (response?.detail || 'Unknown error'));
    }
    req.session.user = response.user;
    res.redirect('/');
  });
});

app.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/');
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log('Node server running on port ' + PORT);
});
