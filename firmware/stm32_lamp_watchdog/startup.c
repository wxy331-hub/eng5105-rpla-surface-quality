/* Minimal STM32F446 start-up: vector table, .data copy, .bss clear, then main(). */
#include <stdint.h>

extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
int main(void);
void SysTick_Handler(void);
void USART2_IRQHandler(void);

void Default_Handler(void)
{
    for (;;) { }   /* unexpected exception: stall; the IWDG then resets the MCU */
}

void Reset_Handler(void)
{
    uint32_t *src = &_sidata;
    for (uint32_t *dst = &_sdata; dst < &_edata; ) *dst++ = *src++;
    for (uint32_t *dst = &_sbss; dst < &_ebss; ) *dst++ = 0;
    main();
    for (;;) { }
}

/* 16 core exceptions + 97 STM32F446 interrupts; USART2 is IRQ 38. */
__attribute__((section(".isr_vector"), used))
void (*const vector_table[16 + 97])(void) = {
    [0] = (void (*)(void))&_estack,
    [1] = Reset_Handler,
    [2 ... 14] = Default_Handler,
    [15] = SysTick_Handler,
    [16 ... 16 + 37] = Default_Handler,
    [16 + 38] = USART2_IRQHandler,
    [16 + 39 ... 16 + 96] = Default_Handler,
};
