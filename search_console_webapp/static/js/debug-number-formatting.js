/**
 * ✅ ARCHIVO DE DEBUG PARA PROBAR FORMATEO DE NÚMEROS
 * Incluir este script temporalmente para debugging
 */

// Esperar a que el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
  console.log('🧪 INICIANDO TESTS DE FORMATEO DE NÚMEROS');
  
  // Esperar a que number-utils esté disponible
  setTimeout(() => {
    // Importar funciones dinámicamente
    import('./number-utils.js').then(module => {
      const { 
        formatInteger, 
        formatPercentage, 
        formatDecimal, 
        formatPosition, 
        formatPercentageChange,
        parseIntegerValue
      } = module;
      
      console.log('🧪 Testing formatInteger (formateo manual):');
      console.log('formatInteger(9666):', formatInteger(9666));
      console.log('formatInteger(1234567):', formatInteger(1234567)); 
      console.log('formatInteger(45000):', formatInteger(45000));
      console.log('formatInteger(1500):', formatInteger(1500));
      console.log('formatInteger(999):', formatInteger(999));
      console.log('formatInteger(123):', formatInteger(123));
      
              console.log('🧪 Testing formatPercentage (for CTR):');
        console.log('formatPercentage(5.67) [CTR ya en %]:', formatPercentage(5.67));
        console.log('formatPercentage(12.34) [CTR ya en %]:', formatPercentage(12.34));
        console.log('formatPercentage(5.00) [CTR ya en %]:', formatPercentage(5.00));
      
      console.log('🧪 Testing formatDecimal:');
      console.log('formatDecimal(5.67, 2):', formatDecimal(5.67, 2));
      console.log('formatDecimal(12.345, 1):', formatDecimal(12.345, 1));
      
      console.log('🧪 Testing formatPosition:');
      console.log('formatPosition(5.2):', formatPosition(5.2));
      console.log('formatPosition(10.75):', formatPosition(10.75));
      
              console.log('🧪 Testing formatPercentageChange:');
        console.log('formatPercentageChange(15.5):', formatPercentageChange(15.5));
        console.log('formatPercentageChange(-8.2):', formatPercentageChange(-8.2));
        
        console.log('🧪 Testing ordenamiento (parseIntegerValue):');
        const testNumbers = ['45.000', '1.500', '999'];
        const parsed = testNumbers.map(n => ({ original: n, parsed: module.parseIntegerValue(n) }));
        console.log('Números ordenados por valor:', parsed.sort((a, b) => b.parsed - a.parsed));
        
        console.log('🧪 Testing CTR conversion (GSC decimal to percentage):');
        console.log('GSC CTR 0.0567 * 100 =', (0.0567 * 100).toFixed(2), '→ formatPercentage:', module.formatPercentage(0.0567 * 100));
        console.log('GSC CTR 0.1234 * 100 =', (0.1234 * 100).toFixed(2), '→ formatPercentage:', module.formatPercentage(0.1234 * 100));
      
              // Hacer funciones disponibles globalmente para testing manual
        window.debugFormatting = {
          formatInteger,
          formatPercentage,
          formatDecimal,
          formatPosition,
          formatPercentageChange,
          parseIntegerValue
        };
      
              console.log('✅ Funciones de formateo disponibles en window.debugFormatting');
        console.log('🧪 Ejemplos:');
        console.log('  window.debugFormatting.formatInteger(45000) // Debería devolver "45.000"');
        console.log('  window.debugFormatting.parseIntegerValue("45.000") // Debería devolver 45000');
        console.log('  window.debugFormatting.formatPercentage(5.67) // Para CTR ya en %');
      
    }).catch(error => {
      console.error('❌ Error importando number-utils:', error);
    });
  }, 1000);
}); 