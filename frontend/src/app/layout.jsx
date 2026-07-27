import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import "./globals.css";
import "./Layout.css";
import Providers from "@/components/providers/Providers";
import { AppAuthProvider } from "@/lib/auth";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="root-body">
        <ThemeProvider
          attribute="class"
          forcedTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <AppAuthProvider>
            <Providers>
              <div className="root-wrapper">
                {/* Background glow effects */}
                <div className="glow-top-left" />
                <div className="glow-bottom-right" />
                
                {children}
              </div>
            </Providers>
          </AppAuthProvider>
          <Toaster richColors position="top-center" />
        </ThemeProvider>
      </body>
    </html>
  );
}
