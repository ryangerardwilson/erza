import "./globals.css";

export const metadata = {
  title: "erza docs",
  description: "Human docs, agent docs, and worked examples for erza."
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
