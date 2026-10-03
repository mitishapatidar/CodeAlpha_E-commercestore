// Adapted from the "animated-ai-chat" shadcn-style component.
// Changes for NovaMart: "use client" removed (Vite, not Next.js); the fake 3-second send is replaced by an
// `onSubmit` prop wired to the real agent; `busy` drives the thinking state; title, placeholder, assistant name
// and slash-commands are props; accent colours follow the NovaMart red→orange theme.
import { AnimatePresence, motion } from "framer-motion";
import { Command, LoaderIcon, Paperclip, SendIcon, XIcon } from "lucide-react";
import * as React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface UseAutoResizeTextareaProps {
  minHeight: number;
  maxHeight?: number;
}

function useAutoResizeTextarea({ minHeight, maxHeight }: UseAutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      if (reset) {
        textarea.style.height = `${minHeight}px`;
        return;
      }
      textarea.style.height = `${minHeight}px`;
      const newHeight = Math.max(minHeight, Math.min(textarea.scrollHeight, maxHeight ?? Number.POSITIVE_INFINITY));
      textarea.style.height = `${newHeight}px`;
    },
    [minHeight, maxHeight],
  );

  useEffect(() => {
    if (textareaRef.current) textareaRef.current.style.height = `${minHeight}px`;
  }, [minHeight]);

  useEffect(() => {
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

export interface CommandSuggestion {
  icon: React.ReactNode;
  label: string;
  description: string;
  prefix: string;
  /** Text placed in the input when the command is picked (defaults to the prefix). */
  template?: string;
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  containerClassName?: string;
  showRing?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, containerClassName, showRing = true, onFocus, onBlur, ...props }, ref) => {
    const [isFocused, setIsFocused] = React.useState(false);
    return (
      <div className={cn("relative", containerClassName)}>
        <textarea
          className={cn(
            "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "transition-all duration-200 ease-in-out",
            "placeholder:text-muted-foreground",
            "disabled:cursor-not-allowed disabled:opacity-50",
            showRing ? "focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0" : "",
            className,
          )}
          ref={ref}
          onFocus={(e) => {
            setIsFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setIsFocused(false);
            onBlur?.(e);
          }}
          {...props}
        />
        {showRing && isFocused && (
          <motion.span
            className="pointer-events-none absolute inset-0 rounded-md ring-2 ring-orange-500/30 ring-offset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";

export interface AnimatedAIChatProps {
  title?: string;
  subtitle?: string;
  placeholder?: string;
  assistantName?: string;
  commands?: CommandSuggestion[];
  /** Called with the message when the user sends. If omitted, the component runs its original demo behaviour. */
  onSubmit?: (text: string) => void;
  /** True while the agent is working (shows the thinking pill and disables send). */
  busy?: boolean;
  disabled?: boolean;
  className?: string;
}

export function AnimatedAIChat({
  title = "How can I help today?",
  subtitle = "Type a command or ask a question",
  placeholder = "Ask a question...",
  assistantName = "AI",
  commands = [],
  onSubmit,
  busy = false,
  disabled = false,
  className,
}: AnimatedAIChatProps) {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [demoTyping, setDemoTyping] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState<number>(-1);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 60, maxHeight: 200 });
  const [inputFocused, setInputFocused] = useState(false);
  const commandPaletteRef = useRef<HTMLDivElement>(null);
  const isTyping = busy || demoTyping;

  useEffect(() => {
    if (value.startsWith("/") && !value.includes(" ")) {
      setShowCommandPalette(true);
      setActiveSuggestion(commands.findIndex((cmd) => cmd.prefix.startsWith(value)));
    } else {
      setShowCommandPalette(false);
    }
  }, [value, commands]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => setMousePosition({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const commandButton = document.querySelector("[data-command-button]");
      if (commandPaletteRef.current && !commandPaletteRef.current.contains(target) && !commandButton?.contains(target)) {
        setShowCommandPalette(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const applyCommand = (index: number) => {
    const c = commands[index];
    if (!c) return;
    setValue(c.template ?? `${c.prefix} `);
    setShowCommandPalette(false);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      adjustHeight();
    });
  };

  const handleSendMessage = () => {
    const text = value.trim();
    if (!text || isTyping || disabled) return;
    if (onSubmit) {
      onSubmit(text);
    } else {
      setDemoTyping(true);
      setTimeout(() => setDemoTyping(false), 3000);
    }
    setValue("");
    adjustHeight(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommandPalette && commands.length) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveSuggestion((prev) => (prev < commands.length - 1 ? prev + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveSuggestion((prev) => (prev > 0 ? prev - 1 : commands.length - 1));
      } else if (e.key === "Tab" || e.key === "Enter") {
        e.preventDefault();
        if (activeSuggestion >= 0) applyCommand(activeSuggestion);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setShowCommandPalette(false);
      }
    } else if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleAttachFile = () => setAttachments((prev) => [...prev, `photo-${Math.floor(Math.random() * 1000)}.jpg`]);
  const removeAttachment = (index: number) => setAttachments((prev) => prev.filter((_, i) => i !== index));

  return (
    <div className={cn("relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-transparent p-6 text-white", className)}>
      <div className="absolute inset-0 h-full w-full overflow-hidden" aria-hidden>
        <div className="absolute left-1/4 top-0 h-96 w-96 animate-pulse rounded-full bg-orange-500/10 mix-blend-normal blur-[128px] filter" />
        <div className="absolute bottom-0 right-1/4 h-96 w-96 animate-pulse rounded-full bg-rose-500/10 mix-blend-normal blur-[128px] filter delay-700" />
        <div className="absolute right-1/3 top-1/4 h-64 w-64 animate-pulse rounded-full bg-amber-500/10 mix-blend-normal blur-[96px] filter delay-1000" />
      </div>
      <div className="relative mx-auto w-full max-w-2xl">
        <motion.div className="relative z-10 space-y-10" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: "easeOut" }}>
          <div className="space-y-3 text-center">
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }} className="inline-block">
              <h1 className="bg-gradient-to-r from-white/90 to-white/40 bg-clip-text pb-1 text-3xl font-medium tracking-tight text-transparent">{title}</h1>
              <motion.div
                className="h-px bg-gradient-to-r from-transparent via-orange-300/40 to-transparent"
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: "100%", opacity: 1 }}
                transition={{ delay: 0.5, duration: 0.8 }}
              />
            </motion.div>
            <motion.p className="text-sm text-white/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
              {subtitle}
            </motion.p>
          </div>

          <motion.div
            className="relative rounded-2xl border border-white/[0.06] bg-white/[0.02] shadow-2xl backdrop-blur-2xl"
            initial={{ scale: 0.98 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.1 }}
          >
            <AnimatePresence>
              {showCommandPalette && commands.length > 0 && (
                <motion.div
                  ref={commandPaletteRef}
                  className="absolute bottom-full left-4 right-4 z-50 mb-2 overflow-hidden rounded-lg border border-white/10 bg-black/90 shadow-lg backdrop-blur-xl"
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 5 }}
                  transition={{ duration: 0.15 }}
                  role="listbox"
                  aria-label="Commands"
                >
                  <div className="bg-black/95 py-1">
                    {commands.map((s, index) => (
                      <motion.div
                        key={s.prefix}
                        role="option"
                        aria-selected={activeSuggestion === index}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 px-3 py-2 text-xs transition-colors",
                          activeSuggestion === index ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5",
                        )}
                        onClick={() => applyCommand(index)}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: index * 0.03 }}
                      >
                        <div className="flex h-5 w-5 items-center justify-center text-white/60">{s.icon}</div>
                        <div className="font-medium">{s.label}</div>
                        <div className="ml-1 text-xs text-white/40">{s.prefix}</div>
                        <div className="ml-auto hidden truncate text-white/30 sm:block">{s.description}</div>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="p-4">
              <label htmlFor="ai-chat-input" className="sr-only">
                {placeholder}
              </label>
              <Textarea
                id="ai-chat-input"
                ref={textareaRef}
                value={value}
                disabled={disabled}
                onChange={(e) => {
                  setValue(e.target.value);
                  adjustHeight();
                }}
                onKeyDown={handleKeyDown}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                placeholder={placeholder}
                containerClassName="w-full"
                className="min-h-[60px] w-full resize-none border-none bg-transparent px-4 py-3 text-sm text-white/90 placeholder:text-white/25 focus:outline-none"
                style={{ overflow: "hidden" }}
                showRing={false}
              />
            </div>

            <AnimatePresence>
              {attachments.length > 0 && (
                <motion.div className="flex flex-wrap gap-2 px-4 pb-3" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                  {attachments.map((file, index) => (
                    <motion.div
                      key={file + index}
                      className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-3 py-1.5 text-xs text-white/70"
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.9 }}
                    >
                      <span>{file}</span>
                      <button type="button" aria-label={`Remove ${file}`} onClick={() => removeAttachment(index)} className="text-white/40 transition-colors hover:text-white">
                        <XIcon className="h-3 w-3" />
                      </button>
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex items-center justify-between gap-4 border-t border-white/[0.05] p-4">
              <div className="flex items-center gap-3">
                <motion.button
                  type="button"
                  aria-label="Attach a photo"
                  onClick={handleAttachFile}
                  whileTap={{ scale: 0.94 }}
                  className="group relative rounded-lg p-2 text-white/40 transition-colors hover:text-white/90"
                >
                  <Paperclip className="h-4 w-4" />
                  <span className="absolute inset-0 rounded-lg bg-white/[0.05] opacity-0 transition-opacity group-hover:opacity-100" />
                </motion.button>
                {commands.length > 0 && (
                  <motion.button
                    type="button"
                    aria-label="Show commands"
                    data-command-button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowCommandPalette((prev) => !prev);
                    }}
                    whileTap={{ scale: 0.94 }}
                    className={cn(
                      "group relative rounded-lg p-2 text-white/40 transition-colors hover:text-white/90",
                      showCommandPalette && "bg-white/10 text-white/90",
                    )}
                  >
                    <Command className="h-4 w-4" />
                    <span className="absolute inset-0 rounded-lg bg-white/[0.05] opacity-0 transition-opacity group-hover:opacity-100" />
                  </motion.button>
                )}
              </div>

              <motion.button
                type="button"
                onClick={handleSendMessage}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                disabled={isTyping || disabled || !value.trim()}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all",
                  value.trim() ? "bg-white text-[#0A0A0B] shadow-lg shadow-white/10" : "bg-white/[0.05] text-white/40",
                )}
              >
                {isTyping ? <LoaderIcon className="h-4 w-4 animate-[spin_2s_linear_infinite]" /> : <SendIcon className="h-4 w-4" />}
                <span>Send</span>
              </motion.button>
            </div>
          </motion.div>

          {commands.length > 0 && (
            <div className="flex flex-wrap items-center justify-center gap-2">
              {commands.map((s, index) => (
                <motion.button
                  key={s.prefix}
                  type="button"
                  onClick={() => applyCommand(index)}
                  className="group relative flex items-center gap-2 rounded-lg bg-white/[0.02] px-3 py-2 text-sm text-white/60 transition-all hover:bg-white/[0.05] hover:text-white/90"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  {s.icon}
                  <span>{s.label}</span>
                  <span className="absolute inset-0 rounded-lg border border-white/[0.05]" />
                </motion.button>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      <AnimatePresence>
        {isTyping && (
          <motion.div
            className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded-full border border-white/[0.05] bg-white/[0.02] px-4 py-2 shadow-lg backdrop-blur-2xl"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            aria-live="polite"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-7 min-w-8 items-center justify-center rounded-full bg-white/[0.05] px-2 text-center">
                <span className="mb-0.5 text-xs font-medium text-white/90">{assistantName}</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-white/70">
                <span>Verifying</span>
                <TypingDots />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {inputFocused && (
        <motion.div
          className="pointer-events-none fixed z-0 h-[50rem] w-[50rem] rounded-full bg-gradient-to-r from-rose-500 via-orange-500 to-amber-500 opacity-[0.02] blur-[96px]"
          animate={{ x: mousePosition.x - 400, y: mousePosition.y - 400 }}
          transition={{ type: "spring", damping: 25, stiffness: 150, mass: 0.5 }}
          aria-hidden
        />
      )}
    </div>
  );
}

function TypingDots() {
  return (
    <div className="ml-1 flex items-center">
      {[1, 2, 3].map((dot) => (
        <motion.div
          key={dot}
          className="mx-0.5 h-1.5 w-1.5 rounded-full bg-white/90"
          initial={{ opacity: 0.3 }}
          animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.85, 1.1, 0.85] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: dot * 0.15, ease: "easeInOut" }}
          style={{ boxShadow: "0 0 4px rgba(255, 255, 255, 0.3)" }}
        />
      ))}
    </div>
  );
}
