import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import ProjectServiceListPage, { clientLoader } from "./project-service-list";
import { type ServiceCardResponse } from "~/lib/queries"; // Assuming this type is exported or find correct type
import { RouterProvider, createMemoryRouter, Outlet, useFetcher } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { href } from "react-router"; // For action path construction

// Mock useFetcher
const mockBulkSubmit = vi.fn();
const mockBulkFetcher = {
  Form: ({ children, method, action, ...props }: any) => (
    <form
      data-testid="bulk-fetcher-form" // Add data-testid for specific targeting
      onSubmit={(e) => {
        e.preventDefault();
        const formData = new FormData(e.target as HTMLFormElement);
        mockBulkSubmit(formData, { method, action });
      }}
      {...props}
    >
      {children}
    </form>
  ),
  load: vi.fn(),
  submit: mockBulkSubmit,
  state: "idle",
  data: null,
  formData: null,
};

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useFetcher: (args: any) => {
        // Allow specific fetcher for specific forms if needed, or just return one mock
        return mockBulkFetcher;
    },
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
    useNavigate: () => vi.fn(),
  };
});

vi.mock("~/lib/queries", () => ({
  projectQueries: {
    serviceList: vi.fn().mockReturnValue({ queryKey: ["project-service-list"], queryFn: async () => ([]) }),
  },
}));

const queryClient = new QueryClient();

const mockServiceList: ServiceCardResponse[] = [
  { id: "service1", slug: "s1", type: "docker", image: "img1", tag: "latest", status: "HEALTHY", updatedAt: new Date().toISOString(), url: null, volumeNumber: 0, selected: false, onToggleSelect: vi.fn() },
  { id: "service2", slug: "s2", type: "git", repository: "repo", branch: "main", last_commit_message: "commit", status: "HEALTHY", updatedAt: new Date().toISOString(), url: null, volumeNumber: 0, selected: false, onToggleSelect: vi.fn() },
];

const mockLoaderData = { serviceList: mockServiceList };
const mockParams = { projectSlug: "test-project", envSlug: "production" };

const renderComponent = (initialData = mockLoaderData) => {
    const router = createMemoryRouter([
    { 
        path: "/project/:projectSlug/:envSlug", 
        element: (
            <QueryClientProvider client={queryClient}>
                <ProjectServiceListPage params={mockParams} loaderData={initialData.serviceList} />
            </QueryClientProvider>
        ),
        loader: async () => initialData, // Mock loader for the route
    }
    ], {
        initialEntries: ["/project/test-project/production"],
    });
    return render(<RouterProvider router={router} />);
};


describe("ProjectServiceListPage - Bulk Deploy Actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBulkFetcher.state = "idle";
    mockBulkFetcher.data = null;
    // Mock the projectQueries.serviceList to return our mock data for each test
    (projectQueries.serviceList as any).mockReturnValue({ 
        queryKey: ["project-service-list"], 
        queryFn: async () => mockServiceList,
        initialData: mockServiceList 
    });
  });

  const openBulkActionsPopover = async () => {
    // Simulate selecting a service to make the toast with actions appear
    // The actual selection logic might need more specific targeting if checkboxes are used per service
    // For now, let's assume the "actions" button becomes available after some selection.
    // This part is tricky as the toast is imperative. We might need to trigger selection first.
    
    // Click on a service card to select it (assuming this makes the toast appear)
    // This needs to match how selection is actually handled to trigger the toast.
    // If selection is via checkboxes within cards, those need to be targeted.
    // For this example, we'll assume selecting the first service.
    // This is a simplification; real test might need to click a checkbox inside a card.
    const serviceCards = await screen.findAllByRole("article"); // Assuming cards have role article
    if (serviceCards.length > 0) {
         fireEvent.click(serviceCards[0]); // This is a placeholder for actual selection
    }
    
    // Wait for the toast to appear (it contains the "actions" button)
    // This is also tricky as the toast is imperative.
    // A more reliable way might be to have a dedicated "Bulk Actions" button if the toast is hard to test.
    // For now, let's assume the button is eventually visible for selection.
    const actionsButton = await screen.findByRole('button', { name: /actions/i });
    fireEvent.click(actionsButton);
    
    // The popover content with the deploy button should now be visible
    await screen.findByText(/Deploy services/i); // Wait for popover content
  };


  it("shows 'Cancel previous active deployments?' checkbox in bulk deploy popover", async () => {
    renderComponent();
    // Simulate service selection to show the bulk actions toast & popover
    // This will depend on how service selection is implemented.
    // For now, we directly try to find the button that opens the popover.
    // This part of the test needs to correctly trigger the popover.
    // Let's assume selecting the first service makes the popover trigger appear or become active.
    const serviceCards = await screen.findAllByRole("article"); 
    fireEvent.click(screen.getByText(mockServiceList[0].slug)); // Click on the first service card by its slug

    const actionsButton = await screen.findByRole('button', { name: /actions/i });
    fireEvent.click(actionsButton);

    expect(await screen.findByLabelText(/Cancel previous active deployments?/i)).toBeInTheDocument();
  });

  it("checkbox state changes on click in bulk deploy popover", async () => {
    renderComponent();
    const serviceCards = await screen.findAllByRole("article");
    fireEvent.click(screen.getByText(mockServiceList[0].slug)); 
    
    const actionsButton = await screen.findByRole('button', { name: /actions/i });
    fireEvent.click(actionsButton);

    const checkbox = await screen.findByLabelText(/Cancel previous active deployments?/i) as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
  });

  it("submits with cancel_previous_deployments=on for bulk deploy when checkbox is checked", async () => {
    renderComponent();
    const serviceCards = await screen.findAllByRole("article");
    fireEvent.click(screen.getByText(mockServiceList[0].slug)); // Select first service
    fireEvent.click(screen.getByText(mockServiceList[1].slug)); // Select second service

    const actionsButton = await screen.findByRole('button', { name: /actions/i });
    fireEvent.click(actionsButton);

    const checkbox = await screen.findByLabelText(/Cancel previous active deployments?/i);
    fireEvent.click(checkbox); // Check it

    const deployButton = screen.getByRole('button', { name: /Deploy services/i });
    fireEvent.click(deployButton);

    expect(mockBulkSubmit).toHaveBeenCalled();
    const submittedFormData = mockBulkSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.getAll("service_id")).toEqual(["service1", "service2"]);
    expect(submittedFormData.get("cancel_previous_deployments")).toBe("on");
    expect(mockBulkSubmit.mock.calls[0][1].action).toBe(`/project/${mockParams.projectSlug}/${mockParams.envSlug}/bulk-deploy-services`);
  });

  it("submits without cancel_previous_deployments for bulk deploy when checkbox is unchecked", async () => {
    renderComponent();
    const serviceCards = await screen.findAllByRole("article");
    fireEvent.click(screen.getByText(mockServiceList[0].slug));

    const actionsButton = await screen.findByRole('button', { name: /actions/i });
    fireEvent.click(actionsButton);
    
    // Checkbox is unchecked by default
    const deployButton = screen.getByRole('button', { name: /Deploy services/i });
    fireEvent.click(deployButton);

    expect(mockBulkSubmit).toHaveBeenCalled();
    const submittedFormData = mockBulkSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.get("cancel_previous_deployments")).toBeNull();
  });
});

// Minimal setup for FieldSetCheckbox and FieldSetLabel if not globally available
vi.mock("~/components/ui/fieldset", async () => {
  const actual = await vi.importActual("~/components/ui/fieldset");
  return {
    ...actual,
    FieldSet: ({ children, ...props }: any) => <div data-testid="fieldset" {...props}>{children}</div>,
    FieldSetCheckbox: (props: any) => <input type="checkbox" data-testid="fieldset-checkbox" {...props} />,
    FieldSetLabel: ({ children, ...props }: any) => <label {...props}>{children}</label>,
  };
});
vi.mock("~/components/ui/button", async() => {
  const actual = await vi.importActual("~/components/ui/button");
  return {
    ...actual,
    Button: ({children, ...props}: any) => <button {...props}>{children}</button>,
    SubmitButton: ({children, ...props}: any) => <button type="submit" {...props}>{children}</button>,
  }
});
vi.mock("~/components/ui/popover", async () => {
    const actual = await vi.importActual("@radix-ui/react-popover");
    return {
        ...actual,
        Popover: ({ children } : {children: React.ReactNode}) => <div>{children}</div>,
        PopoverTrigger: ({ children, ...props } : {children: React.ReactNode, props?: any}) => <div {...props}>{children}</div>,
        PopoverContent: ({ children, ...props } : {children: React.ReactNode, props?: any}) => <div {...props}>{children}</div>,
    };
});
// Mock service cards if they interfere with selection logic or rendering
vi.mock("~/components/service-cards", () => ({
    DockerServiceCard: ({slug, onToggleSelect, id}: any) => <article onClick={() => onToggleSelect(id)}>{slug}</article>,
    GitServiceCard: ({slug, onToggleSelect, id}: any) => <article onClick={() => onToggleSelect(id)}>{slug}</article>,
}));
