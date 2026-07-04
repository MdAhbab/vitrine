import { useEffect, useState } from "react";
import { Toaster as Sonner, ToasterProps } from "sonner";

/** Reads the app's real theme (the `.dark` class set by lib/theme.ts) and
 * tracks changes so toasts always match the active palette. */
function useDocumentTheme(): "light" | "dark" {
  const [mode, setMode] = useState<"light" | "dark">(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setMode(document.documentElement.classList.contains("dark") ? "dark" : "light");
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return mode;
}

const Toaster = ({ ...props }: ToasterProps) => {
  const theme = useDocumentTheme();

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
        } as React.CSSProperties
      }
      {...props}
    />
  );
};

export { Toaster };
