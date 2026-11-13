import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './app/globals.css'
import Providers from './components/providers/Providers.jsx'
import { AppAuthProvider } from './lib/auth.jsx'
import { ThemeProvider } from 'next-themes'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem={true}
      storageKey="site-studio-theme"
      disableTransitionOnChange={false}
    >
      <AppAuthProvider>
        <Providers>
          <App />
        </Providers>
      </AppAuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
