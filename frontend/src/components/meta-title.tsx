import type { FC } from "react";

type MetaTitleProps = {
  title: string;
};

export const MetaTitle: FC<MetaTitleProps> = ({ title }) => (
  <title>{`${title} | ZaneOps`}</title>
);
