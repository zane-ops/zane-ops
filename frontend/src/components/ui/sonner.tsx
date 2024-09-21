import { Toaster as Sonner } from "sonner";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="system"
      className="toaster group "
      toastOptions={{
        classNames: {
          toast:
            "group toaster group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          title: "text-card-foreground",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          error: "[&_svg]:text-red-400",
          success: "[&_svg]:text-green-400",
          icon: "icon",
          closeButton: "border-border [&_svg]:text-foreground"
        }
      }}
      {...props}
    />
  );
};

export { Toaster };
