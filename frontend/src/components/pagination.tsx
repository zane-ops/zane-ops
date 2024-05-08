import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { Button } from "./ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";

export type PaginationProps = {
  totalPages: number;
  currentPage: number;
  perPage: number;
  className?: string;
  onChangePage: (page: number) => void;
  onChangePerPage: (perPage: number) => void;
};

export function Pagination({
  totalPages,
  currentPage,
  perPage,
  className = "",
  onChangePage,
  onChangePerPage,
}: PaginationProps) {
  return (
    <div className={`flex items-center justify-end px-2 ${className}`}>
      <div className="flex items-center space-x-2">
        <p className="text-sm font-medium">Rows per page</p>
        <Select
          value={`${perPage}`}
          onValueChange={(value) => onChangePerPage(Number(value))}
        >
          <SelectTrigger className="h-8 w-[70px]">
            <SelectValue placeholder={`${perPage}`} />
          </SelectTrigger>
          <SelectContent className="border border-border" side="top">
            {[10, 20, 30, 40, 50].map((pageSize) => (
              <SelectItem key={pageSize} value={`${pageSize}`}>
                {pageSize}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center space-x-6 lg:space-x-8">
        <div className="flex w-[100px] items-center justify-center text-sm font-medium">
          Page {currentPage} of {totalPages}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            className={`hidden h-8 w-8 p-0 lg:flex ${
              currentPage === 1 ? "opacity-50 pointer-events-none" : ""
            }`}
            onClick={() => onChangePage(1)}
            disabled={currentPage === 1}
          >
            <span className="sr-only">Go to first page</span>
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className={`h-8 w-8 p-0 ${
              currentPage === 1 ? "opacity-50 pointer-events-none" : ""
            }`}
            onClick={() => onChangePage(currentPage - 1)}
            disabled={currentPage === 1}
          >
            <span className="sr-only">Go to previous page</span>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className={`h-8 w-8 p-0 ${
              currentPage === totalPages ? "opacity-50 pointer-events-none" : ""
            }`}
            onClick={() => onChangePage(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            <span className="sr-only">Go to next page</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            className={`hidden h-8 w-8 p-0 lg:flex ${
              currentPage === totalPages ? "opacity-50 pointer-events-none" : ""
            }`}
            onClick={() => onChangePage(totalPages)}
            disabled={currentPage === totalPages}
          >
            <span className="sr-only">Go to last page</span>
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
