import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { ServiceChangesModal } from "./service-changes-modal";
import { type Service } from "~/lib/queries";
import { type Environment } from "~/lib/types";
import {RouterProvider, createMemoryRouter, Outlet } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock useFetcher
const mockSubmit = vi.fn();
const mockFetcher = {
  Form: ({ children, method, action, ...props }: any) => (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const formData = new FormData(e.target as HTMLFormElement);
        mockSubmit(formData, { method, action });
      }}
      {...props}
    >
      {children}
    </form>
  ),
  load: vi.fn(),
  submit: mockSubmit, // Use the spy here
  state: "idle",
  data: null,
  formData: null,
};
vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useFetcher: () => mockFetcher,
    useNavigate: () => vi.fn(), // Mock useNavigate as it's used internally
  };
});

// Mock for projectQueries and queryClient if needed for context, though not directly tested here
vi.mock("~/lib/queries", () => ({
  serviceQueries: {
    single: vi.fn().mockReturnValue({ queryKey: ["service-single"], queryFn: async () => ({}) }),
  },
}));
const queryClient = new QueryClient();


const mockDockerService: Service = {
  id: "docker-service-id",
  slug: "my-docker-service",
  type: "DOCKER_REGISTRY",
  image: "nginx:latest",
  project_id: "project-1",
  environment: { id: "env-1", name: "production", is_preview: false, variables: [] } as Environment,
  unapplied_changes: [
    { id: "change-1", field: "source", type: "UPDATE", new_value: { image: "nginx:alpine" }, old_value: {image: "nginx:latest"}, item_id: null },
  ],
  // Add other necessary fields for Service type
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  command: null,
  builder: null,
  repository_url: null,
  branch_name: null,
  commit_sha: null,
  dockerfile_builder_options: null,
  static_dir_builder_options: null,
  nixpacks_builder_options: null,
  railpack_builder_options: null,
  healthcheck: null,
  credentials: null,
  urls: [],
  volumes: [],
  deploy_token: "token",
  ports: [],
  env_variables: [],
  network_aliases: [],
  network_alias: "alias",
  resource_limits: null,
  system_env_variables: [],
  configs: [],
};

const mockGitService: Service = {
  ...mockDockerService, // Base it on docker, then override
  id: "git-service-id",
  slug: "my-git-service",
  type: "GIT_REPOSITORY",
  image: null, // Git services don't have an image directly
  repository_url: "https://github.com/example/repo.git",
  branch_name: "main",
  builder: "DOCKERFILE", // Example builder
  dockerfile_builder_options: { dockerfile_path: "./Dockerfile", build_context_dir: "./", build_stage_target: null },
  unapplied_changes: [
     { id: "change-git-1", field: "git_source", type: "UPDATE", new_value: { commit_sha: "newsha" }, old_value: {commit_sha: "oldsha"}, item_id: null },
  ],
};


// Helper to render with router context
const renderWithRouter = (ui: React.ReactElement) => {
  const router = createMemoryRouter([ { path: "/", element: <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider> } ], {
    initialEntries: ["/"],
  });
  return render(<RouterProvider router={router} />);
};


describe("ServiceChangesModal", () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks();
    mockFetcher.state = "idle";
    mockFetcher.data = null;
  });

  it("should show 'Cancel previous active deployments?' checkbox for Docker service", () => {
    renderWithRouter(
      <ServiceChangesModal service={mockDockerService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i)); // Open the modal
    expect(screen.getByLabelText(/Cancel previous active deployments?/i)).toBeInTheDocument();
  });

  it("should show 'Cancel previous active deployments?' checkbox for Git service", () => {
    renderWithRouter(
      <ServiceChangesModal service={mockGitService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i)); // Open the modal
    expect(screen.getByLabelText(/Cancel previous active deployments?/i)).toBeInTheDocument();
  });

  it("checkbox state changes on click", () => {
    renderWithRouter(
      <ServiceChangesModal service={mockDockerService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i));
    const checkbox = screen.getByLabelText(/Cancel previous active deployments?/i) as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
  });

  it("submits with cancel_previous_deployments=on for Docker when checkbox is checked", async () => {
    renderWithRouter(
      <ServiceChangesModal service={mockDockerService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i)); // Open modal

    const checkbox = screen.getByLabelText(/Cancel previous active deployments?/i);
    fireEvent.click(checkbox); // Check it

    const deployButton = screen.getByRole('button', { name: /Deploy now/i });
    fireEvent.click(deployButton);
    
    // Check the arguments of the last call to fetcher.Form (indirectly, its action)
    // The form data is handled by the browser/testing-library's form submission simulation
    // We need to ensure our mockFetcher.Form captures the form data correctly if we were to inspect it
    // For now, this test structure assumes the default browser behavior for checkbox submission ("on" if checked)
    // and that the action route will receive it.
    // A more robust way would be to spy on FormData construction or the actual action call.
    // Since we are mocking useFetcher, the submit call is what we check.
    
    // The form data is constructed by the browser/testing-library form submission.
    // We expect `cancel_previous_deployments` to be "on".
    // The actual assertion of what the action receives would be in the action's test.
    // Here, we ensure the form is submitted.
    // The actual form data is not directly inspectable on mockFetcher.submit without custom logic.
    // We will verify the data in the action tests of deploy-docker-service.tsx
    // expect(mockFetcher.Form).toHaveBeenCalled(); // Form is implicitly tested by submit
    expect(mockSubmit).toHaveBeenCalled();
    const submittedFormData = mockSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.get("cancel_previous_deployments")).toBe("on");
    expect(mockSubmit.mock.calls[0][1].action).toBe("./deploy-docker-service");
  });

   it("submits with cancel_previous_deployments=on for Git when checkbox is checked", async () => {
    renderWithRouter(
      <ServiceChangesModal service={mockGitService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i)); 

    const checkbox = screen.getByLabelText(/Cancel previous active deployments?/i);
    fireEvent.click(checkbox); 

    const deployButton = screen.getByRole('button', { name: /Deploy now/i });
    fireEvent.click(deployButton);
    
    // expect(mockFetcher.Form).toHaveBeenCalled();
    expect(mockSubmit).toHaveBeenCalled();
    const submittedFormData = mockSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.get("cancel_previous_deployments")).toBe("on");
    expect(mockSubmit.mock.calls[0][1].action).toBe("./deploy-git-service");
  });


  it("submits without cancel_previous_deployments for Docker when checkbox is unchecked", async () => {
    renderWithRouter(
      <ServiceChangesModal service={mockDockerService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i));

    // Checkbox is unchecked by default
    const deployButton = screen.getByRole('button', { name: /Deploy now/i });
    fireEvent.click(deployButton);

    // We check that the form was submitted. The action test for deploy-docker-service.tsx
    // would verify that cancel_previous_deployments is false or undefined.
    // expect(mockFetcher.Form).toHaveBeenCalled();
    expect(mockSubmit).toHaveBeenCalled();
    const submittedFormData = mockSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.get("cancel_previous_deployments")).toBeNull(); // Or undefined, depending on FormData behavior for unchecked boxes
  });

  it("submits without cancel_previous_deployments for Git when checkbox is unchecked", async () => {
    renderWithRouter(
      <ServiceChangesModal service={mockGitService} project_slug="test-project" />
    );
    fireEvent.click(screen.getByText(/1 unapplied change/i));

    // Checkbox is unchecked by default
    const deployButton = screen.getByRole('button', { name: /Deploy now/i });
    fireEvent.click(deployButton);
    
    expect(mockSubmit).toHaveBeenCalled();
    const submittedFormData = mockSubmit.mock.calls[0][0] as FormData;
    expect(submittedFormData.get("cancel_previous_deployments")).toBeNull();
    expect(mockSubmit.mock.calls[0][1].action).toBe("./deploy-git-service");
  });
});

// Minimal setup for FieldSetCheckbox and FieldSetLabel if not globally available
// This is just to make the tests pass if these components are not complex
// and don't have their own side effects that need mocking.
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
})
