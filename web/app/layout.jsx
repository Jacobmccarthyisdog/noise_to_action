import "./globals.css";

export const metadata = {
  title: "From Noise to Action",
  description: "Benchmark-relative portfolio dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
