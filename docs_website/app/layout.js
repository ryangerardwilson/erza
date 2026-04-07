import "./globals.css";

export const metadata = {
  metadataBase: new URL("https://erza.ryangerardwilson.com"),
  title: {
    default: "erza",
    template: "%s | erza"
  },
  description:
    "erza is a terminal-native language project for component-driven interfaces and the future erzanet."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
