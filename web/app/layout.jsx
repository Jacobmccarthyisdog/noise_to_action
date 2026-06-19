import "./globals.css";

export const metadata = {
  title: "From Noise to Action | Earthline Field Ledger",
  description: "Earthline-styled benchmark-relative portfolio field ledger",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
