/*
 * NUCLEO-F446RE test firmware: 20 kHz lamp PWM on PA8 with a USB-serial heartbeat watchdog.
 *
 * The host (Raspberry Pi, or a PC for this test) talks to USART2, which the on-board
 * ST-LINK exposes as a USB virtual COM port (115200 8N1, one ASCII command per line):
 *   HB        heartbeat, sent every 100 ms while the host application is healthy
 *   TIMEOUT   the host application missed its own deadline; heartbeats stop after this
 *   ARM       allow light output again (only from FAULT, and only with a fresh heartbeat)
 *   DUTY,n    target brightness 0-100 %
 *   STATUS    report now
 *   HANG      TEST ONLY: stop the main loop so the independent watchdog resets the MCU
 * The firmware reports "STATE,<NORMAL|SUSPECT|FAULT>,<duty>,<uptime ms>" every second and
 * on every change, and "BOOT,<reset cause>" after reset.
 *
 * States: FAULT (duty 0, power-up default) -> NORMAL on ARM; NORMAL -> SUSPECT on TIMEOUT
 * or 500 ms without HB (light kept); SUSPECT -> NORMAL after 3 consecutive HB, or -> FAULT
 * (duty 0) when 3 s pass first. The IWDG (~1 s) resets the MCU if this loop itself stalls;
 * after any reset the firmware starts in FAULT again.
 *
 * Clock: the reset default 16 MHz HSI is kept (no PLL), so TIM1 and USART2 run at 16 MHz.
 * Register addresses follow RM0390 (STM32F446xx reference manual).
 */
#include <stdint.h>

#define REG(addr) (*(volatile uint32_t *)(addr))

#define RCC_AHB1ENR    REG(0x40023830u)
#define RCC_APB1ENR    REG(0x40023840u)
#define RCC_APB2ENR    REG(0x40023844u)
#define RCC_CSR        REG(0x40023874u)
#define GPIOA_MODER    REG(0x40020000u)
#define GPIOA_OSPEEDR  REG(0x40020008u)
#define GPIOA_PUPDR    REG(0x4002000Cu)
#define GPIOA_BSRR     REG(0x40020018u)
#define GPIOA_AFRL     REG(0x40020020u)
#define GPIOA_AFRH     REG(0x40020024u)
#define TIM1_CR1       REG(0x40010000u)
#define TIM1_EGR       REG(0x40010014u)
#define TIM1_CCMR1     REG(0x40010018u)
#define TIM1_CCER      REG(0x40010020u)
#define TIM1_PSC       REG(0x40010028u)
#define TIM1_ARR       REG(0x4001002Cu)
#define TIM1_CCR1      REG(0x40010034u)
#define TIM1_BDTR      REG(0x40010044u)
#define USART2_SR      REG(0x40004400u)
#define USART2_DR      REG(0x40004404u)
#define USART2_BRR     REG(0x40004408u)
#define USART2_CR1     REG(0x4000440Cu)
#define IWDG_KR        REG(0x40003000u)
#define IWDG_PR        REG(0x40003004u)
#define IWDG_RLR       REG(0x40003008u)
#define IWDG_SR        REG(0x4000300Cu)
#define DBGMCU_APB1_FZ REG(0xE0042008u)
#define SYST_CSR       REG(0xE000E010u)
#define SYST_RVR       REG(0xE000E014u)
#define SYST_CVR       REG(0xE000E018u)
#define NVIC_ISER1     REG(0xE000E104u)

#define CLOCK_HZ       16000000u
#define PWM_HZ         20000u
#define PWM_PERIOD     (CLOCK_HZ / PWM_HZ)      /* 800 timer counts per PWM period */
#define BAUD           115200u

#define HB_TIMEOUT_MS  500u    /* heartbeat silence before SUSPECT */
#define GRACE_MS       3000u   /* time in SUSPECT before the light is switched off */
#define RECOVER_HB     3u      /* consecutive heartbeats that clear SUSPECT */
#define REPORT_MS      1000u
#define DEFAULT_DUTY   50u

enum { NORMAL, SUSPECT, FAULT };
static const char *const STATE_NAME[] = { "NORMAL", "SUSPECT", "FAULT" };

static volatile uint32_t now_ms;
static volatile uint8_t rx_buf[128];
static volatile uint8_t rx_head;                 /* written by the USART2 interrupt only */
static uint8_t rx_tail;

static uint8_t state = FAULT;
static uint8_t target_duty = DEFAULT_DUTY;
static uint8_t duty;
static uint8_t hb_seen;
static uint8_t recover_count;
static uint32_t last_hb_ms, suspect_since_ms, last_report_ms;

void SysTick_Handler(void) { now_ms++; }

void USART2_IRQHandler(void)
{
    uint32_t sr = USART2_SR;
    if (sr & ((1u << 5) | (1u << 3))) {          /* RXNE or ORE: reading DR clears both */
        uint8_t byte = (uint8_t)USART2_DR;
        if (sr & (1u << 5)) {
            rx_buf[rx_head & 127u] = byte;
            rx_head++;
        }
    }
}

static void put_char(char c)
{
    while (!(USART2_SR & (1u << 7))) { }          /* TXE */
    USART2_DR = (uint8_t)c;
}

static void put_str(const char *s)
{
    while (*s) put_char(*s++);
}

static void put_uint(uint32_t v)
{
    char digits[10];
    int n = 0;
    do { digits[n++] = (char)('0' + v % 10u); v /= 10u; } while (v);
    while (n) put_char(digits[--n]);
}

static int same(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}

static void set_duty(uint8_t pct)
{
    duty = pct;
    TIM1_CCR1 = (uint32_t)pct * PWM_PERIOD / 100u;
}

static void report(void)
{
    put_str("STATE,");
    put_str(STATE_NAME[state]);
    put_char(',');
    put_uint(duty);
    put_char(',');
    put_uint(now_ms);
    put_char('\n');
    last_report_ms = now_ms;
}

static void enter(uint8_t next)
{
    state = next;
    if (next == FAULT) {
        set_duty(0);                               /* MOSFET off */
    } else if (next == NORMAL) {
        set_duty(target_duty);
    } else {
        suspect_since_ms = now_ms;                 /* SUSPECT keeps the present duty */
        recover_count = 0;
    }
    report();
}

static void handle_line(const char *line)
{
    uint32_t now = now_ms;
    if (same(line, "HB")) {
        if (now - last_hb_ms > HB_TIMEOUT_MS) recover_count = 0;   /* a gap breaks the run */
        last_hb_ms = now;
        hb_seen = 1;
        if (state == SUSPECT && ++recover_count >= RECOVER_HB) enter(NORMAL);
    } else if (same(line, "TIMEOUT")) {
        if (state == NORMAL) enter(SUSPECT);
    } else if (same(line, "ARM")) {
        if (state == FAULT && hb_seen && now - last_hb_ms <= HB_TIMEOUT_MS) enter(NORMAL);
        else put_str("ERR,ARM\n");
    } else if (line[0] == 'D' && line[1] == 'U' && line[2] == 'T' && line[3] == 'Y' && line[4] == ',') {
        uint32_t value = 0;
        const char *p = line + 5;
        int digits = 0;
        while (*p >= '0' && *p <= '9' && digits < 4) { value = value * 10u + (uint32_t)(*p++ - '0'); digits++; }
        if (digits && !*p && value <= 100u) {
            target_duty = (uint8_t)value;
            if (state == NORMAL) set_duty(target_duty);
            report();
        } else {
            put_str("ERR,DUTY\n");
        }
    } else if (same(line, "STATUS")) {
        report();
    } else if (same(line, "HANG")) {
        put_str("HANGING\n");
        for (;;) { }                               /* no IWDG refresh from here on */
    } else {
        put_str("ERR,UNKNOWN\n");
    }
}

static void poll_rx(void)
{
    static char line[24];
    static uint8_t len;
    while (rx_tail != rx_head) {
        char c = (char)rx_buf[rx_tail & 127u];
        rx_tail++;
        if (c == '\n' || c == '\r') {
            if (len) { line[len] = 0; handle_line(line); len = 0; }
        } else if (c < 0x20 || c > 0x7E) {
            /* line noise (seen once just after reset, when the host opened the port) */
        } else if (len < sizeof line - 1) {
            line[len++] = c;
        } else {
            len = 0;                               /* overlong line: drop it */
        }
    }
}

static void tick(void)
{
    uint32_t now = now_ms;
    if (state == NORMAL && now - last_hb_ms > HB_TIMEOUT_MS) enter(SUSPECT);
    else if (state == SUSPECT && now - suspect_since_ms > GRACE_MS) enter(FAULT);
    if (now - last_report_ms >= REPORT_MS) report();

    /* LD2 (PA5): on in NORMAL, blinking in SUSPECT, off in FAULT */
    int led = state == NORMAL || (state == SUSPECT && ((now / 125u) & 1u));
    GPIOA_BSRR = led ? (1u << 5) : (1u << (5 + 16));

    IWDG_KR = 0xAAAAu;                             /* refresh the independent watchdog */
}

static void report_boot(void)
{
    uint32_t csr = RCC_CSR;
    put_str("BOOT,");
    if (csr & (1u << 29)) put_str("IWDG");
    else if (csr & (1u << 28)) put_str("SOFTWARE");
    else if (csr & (1u << 27)) put_str("POWER_ON");
    else if (csr & (1u << 26)) put_str("RESET_PIN");
    else put_str("OTHER");
    put_char('\n');
    RCC_CSR = csr | (1u << 24);                    /* RMVF: clear the reset flags */
}

int main(void)
{
    RCC_AHB1ENR |= 1u << 0;                        /* GPIOA */
    RCC_APB1ENR |= 1u << 17;                       /* USART2 */
    RCC_APB2ENR |= 1u << 0;                        /* TIM1 */
    (void)RCC_APB2ENR;

    /* TIM1 CH1 PWM, started at 0 % before PA8 is handed to the timer */
    TIM1_PSC = 0;
    TIM1_ARR = PWM_PERIOD - 1u;
    TIM1_CCR1 = 0;
    TIM1_CCMR1 = (6u << 4) | (1u << 3);            /* PWM mode 1, preload */
    TIM1_CCER = 1u << 0;                           /* CC1E, active high */
    TIM1_BDTR = 1u << 15;                          /* MOE */
    TIM1_EGR = 1u << 0;                            /* load preload registers */
    TIM1_CR1 = (1u << 7) | (1u << 0);              /* ARPE, CEN */

    /* PA8 = TIM1_CH1 (AF1, high speed); PA2/PA3 = USART2 TX/RX (AF7); PA5 = LD2 output */
    GPIOA_AFRH = (GPIOA_AFRH & ~0xFu) | 1u;
    GPIOA_AFRL = (GPIOA_AFRL & ~0xFF00u) | (7u << 8) | (7u << 12);
    GPIOA_OSPEEDR |= 3u << 16;
    GPIOA_PUPDR = (GPIOA_PUPDR & ~(3u << 6)) | (1u << 6);
    GPIOA_MODER = (GPIOA_MODER & ~((3u << 16) | (3u << 4) | (3u << 6) | (3u << 10)))
                | (2u << 16) | (2u << 4) | (2u << 6) | (1u << 10);

    USART2_BRR = (CLOCK_HZ + BAUD / 2u) / BAUD;
    USART2_CR1 = (1u << 13) | (1u << 5) | (1u << 3) | (1u << 2);   /* UE, RXNEIE, TE, RE */
    NVIC_ISER1 = 1u << (38 - 32);                  /* USART2 global interrupt */

    SYST_RVR = CLOCK_HZ / 1000u - 1u;              /* 1 ms tick */
    SYST_CVR = 0;
    SYST_CSR = 7u;

    /* IWDG: LSI ~32 kHz / 32 = ~1 kHz, reload 999 -> ~1 s; paused while the core is halted */
    DBGMCU_APB1_FZ |= 1u << 12;
    IWDG_KR = 0xCCCCu;
    IWDG_KR = 0x5555u;
    IWDG_PR = 3u;
    IWDG_RLR = 999u;
    while (IWDG_SR & 3u) { }
    IWDG_KR = 0xAAAAu;

    report_boot();
    set_duty(0);
    report();

    for (;;) {
        poll_rx();
        tick();
    }
}
