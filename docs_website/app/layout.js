import "./globals.css";

export const metadata = {
  metadataBase: new URL("https://erza.ryangerardwilson.com"),
  title: {
    default: "erza",
    template: "%s | erza"
  },
  description: "Canonical erza documentation rendered directly from the repo README."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
