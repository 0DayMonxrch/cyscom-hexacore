const express    = require('express');
const session    = require('express-session');
const http       = require('http');
const https      = require('https');
const bodyParser = require('body-parser');
const path       = require('path');
const url        = require('url');

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
const PYTHON_BASE_URL = process.env.PYTHON_URL || 'http://127.0.0.1:8080';

function callPython(pathName, payload, callback) {
  const data      = JSON.stringify(payload);
  const parsedUrl = url.parse(PYTHON_BASE_URL + pathName);
  const isHttps   = parsedUrl.protocol === 'https:';
  const lib       = isHttps ? https : http;
  const options   = {
    hostname: parsedUrl.hostname,
    port    : parsedUrl.port || (isHttps ? 443 : 80),
    path    : parsedUrl.path,
    method  : 'POST',
    headers : {
      'Content-Type'  : 'application/json',
      'Content-Length': Buffer.byteLength(data),
    },
  };
  const req = lib.request(options, (res) => {
    let body = '';
    res.on('data', (chunk) => (body += chunk));
    res.on('end', () => {
      try { callback(null, res.statusCode, JSON.parse(body)); }
      catch (err) { callback(err); }
    });
  });
  req.on('error', (err) => { console.error('Error calling Python:', err); callback(err); });
  req.write(data);
  req.end();
}

// Convenience wrappers
function pyPost(path, payload, cb) { callPython(path, payload, cb); }

// ---------- Routes ----------
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/session', (req, res) => {
  if (req.session.user) res.json({ loggedIn: true, user: req.session.user });
  else res.json({ loggedIn: false });
});

// ---- Standard login (userid + password) ----
app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'login.html'));
});

app.post('/login', (req, res) => {
  const { userid, password } = req.body;
  if (!userid || !password) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/login', { userid, password }, (err, status, response) => {
    if (err || response.status !== 'success') {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    req.session.user = response.user;
    res.json({ status: 'success', user: response.user });
  });
});

// ---- Standard register (userid + password) ----
app.get('/register', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'register.html'));
});

app.post('/register', (req, res) => {
  const { userid, password } = req.body;
  if (!userid || !password) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/register', { userid, password }, (err, status, response) => {
    if (err || response.status !== 'success') {
      return res.status(400).json({ error: response && response.detail ? response.detail : 'Registration failed' });
    }
    req.session.user = response.user;
    res.json({ status: 'success', user: response.user });
  });
});

// ---- Email register: create account + trigger OTP ----
app.post('/register-email', (req, res) => {
  const { userid, password } = req.body;
  if (!userid || !password) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/register-email', { userid, password }, (err, status, response) => {
    if (err) return res.status(500).json({ error: 'Server error' });
    if (response.status === 'otp_sent') {
      req.session.pendingEmail = userid.trim().toLowerCase();
      return res.json({ status: 'otp_sent', message: response.message });
    }
    return res.status(status || 400).json({ error: response.detail || 'Registration failed' });
  });
});

// ---- Send OTP (for login-by-otp flow) ----
app.post('/send-otp', (req, res) => {
  const { email, purpose } = req.body;
  if (!email || !purpose) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/send-otp', { email, purpose }, (err, status, response) => {
    if (err) return res.status(500).json({ error: 'Server error' });
    if (status === 429) return res.status(429).json({ error: response.detail });
    if (response.status === 'otp_sent') {
      req.session.pendingEmail = email.trim().toLowerCase();
      return res.json({ status: 'otp_sent', message: response.message });
    }
    return res.status(status || 400).json({ error: response.detail || 'Failed to send OTP' });
  });
});

// ---- Verify OTP ----
app.post('/verify-otp', (req, res) => {
  const { email, otp, purpose } = req.body;
  if (!email || !otp || !purpose) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/verify-otp', { email, otp, purpose }, (err, status, response) => {
    if (err) return res.status(500).json({ error: 'Server error' });
    if (response.status === 'verified' || response.status === 'success') {
      req.session.user = response.user;
      delete req.session.pendingEmail;
      return res.json({ status: 'success', user: response.user });
    }
    return res.status(status || 400).json({ error: response.detail || 'OTP verification failed' });
  });
});

// ---- Email + password login ----
app.post('/login-email', (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) return res.status(400).json({ error: 'Missing fields' });
  pyPost('/login-email', { email, password }, (err, status, response) => {
    if (err) return res.status(500).json({ error: 'Server error' });
    if (response.status === 'success') {
      req.session.user = response.user;
      return res.json({ status: 'success', user: response.user });
    }
    return res.status(status || 401).json({ error: response.detail || 'Login failed' });
  });
});

// ---- Logout ----
app.get('/logout', (req, res) => {
  req.session.destroy(() => { res.redirect('/'); });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log('Node server running on port ' + PORT);
});
