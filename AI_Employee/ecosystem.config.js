// PM2 Process Manager Configuration
// AI Employee — Always-On Watchers (Silver/Gold/Platinum)
//
// Usage:
//   npm install -g pm2
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 startup
//
// Monitor: pm2 status | pm2 logs | pm2 monit
//
// NOTE: Before starting whatsapp-watcher, run whatsapp_setup.bat first (one-time QR scan)

module.exports = {
  apps: [
    // ── INPUT WATCHERS ─────────────────────────────────────
    {
      name: 'gmail-watcher',
      script: 'gmail_watcher.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--loop 120',
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-gmail.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-gmail-error.log',
      time: true,
    },
    {
      name: 'whatsapp-watcher',
      script: 'whatsapp_watcher.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--loop 30',
      watch: false,
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 5,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-whatsapp.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-whatsapp-error.log',
      time: true,
    },
    {
      name: 'filesystem-watcher',
      script: 'watcher.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--loop',
      watch: false,
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-filesystem.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-filesystem-error.log',
      time: true,
    },
    // ── AUTO-POSTERS ───────────────────────────────────────
    {
      name: 'linkedin-autoposter',
      script: 'linkedin_autoposter.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--daemon 9',         // Post daily at 9 AM
      watch: false,
      autorestart: true,
      restart_delay: 30000,
      max_restarts: 5,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-linkedin.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-linkedin-error.log',
      time: true,
    },
    // ── HEALTH MONITOR ────────────────────────────────────
    {
      name: 'watchdog',
      script: 'watchdog.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--loop 300',          // Check every 5 minutes
      watch: false,
      autorestart: true,
      restart_delay: 30000,
      max_restarts: 10,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-watchdog.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-watchdog-error.log',
      time: true,
    },
    // ── PIPELINE PROCESSORS ────────────────────────────────
    {
      name: 'local-agent',
      script: 'local_agent.py',
      interpreter: 'python',
      cwd: __dirname,
      args: '--loop',
      watch: false,
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 5,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-local-agent.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-local-agent-error.log',
      time: true,
    },
    {
      name: 'ralph-loop',
      script: 'ralph_loop.py',
      interpreter: 'python',
      cwd: __dirname,
      watch: false,
      autorestart: true,
      restart_delay: 15000,
      max_restarts: 3,
      env: { PYTHONUNBUFFERED: '1' },
      log_file: 'AI_Employee_Vault/Logs/pm2-ralph.log',
      error_file: 'AI_Employee_Vault/Logs/pm2-ralph-error.log',
      time: true,
    },
  ],
};
