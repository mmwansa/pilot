/* Enable Boostrap tooltips */
$(function () {
  $('[data-toggle="tooltip"]').tooltip({
    trigger : 'hover'
  })

  // Auto-wrap tables so wide content scrolls inside the table container on small screens.
  $('table').each(function () {
    const $table = $(this)
    if ($table.attr('data-no-responsive') === 'true') return
    if ($table.closest('.table-responsive, .table-responsive-sm, .table-responsive-md, .table-responsive-lg, .table-responsive-xl').length) return
    $table.wrap('<div class="table-responsive vacms-table-responsive"></div>')
  })
})
$('#hidden-missing').change(function() {
  $('tr[data-value="N/A"]').toggle();
  $('tr[data-value=""]').toggle();
})
$('#hidden-redacted').change(function() {
  $('tr[data-value="** redacted **"]').toggle();
})
$('tr[data-value="N/A"]').css('display', "none");
$('tr[data-value=""]').css('display',"none");
