import { createContext, useContext } from "react";

/** Follows a new reply's stream in the open thread; outside one, the reply shows when its conversation opens. */
const FollowContext = createContext<(replyId: string, replaces?: string) => void>(() => {});

export const FollowProvider = FollowContext.Provider;
export const useFollow = () => useContext(FollowContext);
